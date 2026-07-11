import threading
import time
from contextlib import contextmanager

from django.conf import settings
from django.db import close_old_connections, connection
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .ai import AiUnavailable, generate_endpoints
from .openapi_import import parse_openapi
from .models import Endpoint, Project, RequestLog, Resource
from .serializers import (
    EndpointSerializer,
    ProjectSerializer,
    RegisterSerializer,
    RequestLogSerializer,
    ResourceSerializer,
)


_GEN_LOCK_NS = 0x6D6B6264  # arbitrary namespace: "mkbd"


@contextmanager
def generation_slot():
    """Server-wide concurrency gate for AI generation, implemented with
    postgres advisory locks so it works across gunicorn workers. Yields
    False when every slot is busy (caller should return 429)."""
    if connection.vendor != "postgresql":  # dev sqlite: no gate
        yield True
        return
    acquired = None
    with connection.cursor() as cur:
        for slot in range(settings.AI_MAX_CONCURRENT):
            cur.execute(
                "SELECT pg_try_advisory_lock(%s, %s)", [_GEN_LOCK_NS, slot]
            )
            if cur.fetchone()[0]:
                acquired = slot
                break
    try:
        yield acquired is not None
    finally:
        if acquired is not None:
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_unlock(%s, %s)",
                    [_GEN_LOCK_NS, acquired],
                )


def seed_resource(endpoint):
    """Ensure a stateful endpoint's Resource exists; seed it from a
    list response_body the first time (e.g. the list endpoint)."""
    if endpoint.mode != "stateful" or not endpoint.resource:
        return
    resource, _ = Resource.objects.get_or_create(
        project=endpoint.project, name=endpoint.resource
    )
    if not resource.initial_items and isinstance(
        endpoint.response_body, list
    ):
        resource.initial_items = endpoint.response_body
        resource.items = endpoint.response_body
        resource.save(update_fields=["initial_items", "items"])


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class OwnedProjectMixin:
    """Scopes nested resources to projects owned by the requester."""

    @property
    def project(self):
        return generics.get_object_or_404(
            Project.objects.filter(owner=self.request.user),
            pk=self.kwargs["project_pk"],
        )


class EndpointViewSet(OwnedProjectMixin, viewsets.ModelViewSet):
    serializer_class = EndpointSerializer

    def get_queryset(self):
        return Endpoint.objects.filter(project=self.project)

    def perform_create(self, serializer):
        endpoint = serializer.save(project=self.project)
        seed_resource(endpoint)


class ResourceListView(OwnedProjectMixin, generics.ListAPIView):
    serializer_class = ResourceSerializer

    def get_queryset(self):
        return Resource.objects.filter(project=self.project)


class ResourceResetView(OwnedProjectMixin, APIView):
    def post(self, request, project_pk, pk):
        resource = generics.get_object_or_404(
            Resource.objects.filter(project=self.project), pk=pk
        )
        resource.reset()
        return Response(ResourceSerializer(resource).data)


class AiGenerateView(OwnedProjectMixin, APIView):
    """Create endpoints in a project from a natural-language
    description, via the AI helper. Rate-limited per user."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request, project_pk):
        """Start generation in the background and return immediately —
        Cloudflare (and most proxies) cut requests at ~100s, which a
        local-model generation can exceed. Clients follow along via the
        progress endpoint, which also delivers success/failure."""
        project = self.project
        description = str(request.data.get("description", "")).strip()
        if not description:
            return Response(
                {"description": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _set_progress(project.pk, 1, "Starting…", "running")
        if getattr(settings, "AI_RUN_SYNC", False):  # tests
            _run_generation(project.pk, description)
        else:
            threading.Thread(
                target=_generation_worker,
                args=(project.pk, description),
                daemon=True,
            ).start()
        return Response({"status": "started"}, status=status.HTTP_202_ACCEPTED)


class _GenerationLog:
    """Collects streamed model output into labeled sections and writes
    it to Project.ai_progress at most ~2x/second (not per token)."""

    MAX_CHARS = 8000

    def __init__(self):
        self._sections: dict[str, str] = {}
        self._lock = threading.Lock()
        self._last_flush = 0.0
        self._dirty = False

    def write(self, label, fragment):
        with self._lock:
            self._sections[label] = (
                self._sections.get(label, "") + fragment
            )[-self.MAX_CHARS:]
            self._dirty = True

    def render(self):
        with self._lock:
            self._dirty = False
            return "\n".join(
                f"── {label} " + "─" * max(1, 40 - len(label))
                + f"\n{text}"
                for label, text in self._sections.items()
            )[-self.MAX_CHARS:]

    def should_flush(self):
        if not self._dirty:
            return False
        now = time.monotonic()
        if now - self._last_flush >= 0.5:
            self._last_flush = now
            return True
        return False


def _set_progress(project_pk, percent, text, state="running", log_text=None):
    payload = {"percent": percent, "text": text, "status": state}
    if log_text is not None:
        payload["log"] = log_text
    Project.objects.filter(pk=project_pk).update(ai_progress=payload)


def _generation_worker(project_pk, description):
    """Thread entrypoint: manage this thread's own DB connections."""
    close_old_connections()
    try:
        _run_generation(project_pk, description)
    finally:
        close_old_connections()


def _run_generation(project_pk, description):
    """Run one AI generation; the outcome lands in ai_progress."""
    gen_log = _GenerationLog()
    state = {"percent": 1, "text": "Starting…"}

    def progress(percent, text):
        state.update(percent=percent, text=text)
        _set_progress(project_pk, percent, text, log_text=gen_log.render())

    def log(label, fragment):
        gen_log.write(label, fragment)
        if gen_log.should_flush():
            _set_progress(
                project_pk, state["percent"], state["text"],
                log_text=gen_log.render(),
            )

    try:
        with generation_slot() as slot_free:
            if not slot_free:
                _set_progress(
                    project_pk, 0,
                    "All AI capacity is in use right now — "
                    "try again in a few seconds.", "error",
                )
                return
            definitions = generate_endpoints(description, progress, log=log)
            project = Project.objects.get(pk=project_pk)
            create_endpoints(project, definitions)
        _set_progress(project_pk, 100, "Done!", "done", gen_log.render())
    except AiUnavailable as exc:
        _set_progress(project_pk, 0, str(exc), "error", gen_log.render())
    except Exception as exc:  # never leave the client polling forever
        _set_progress(
            project_pk, 0, f"Generation failed: {exc}", "error",
            gen_log.render(),
        )


def create_endpoints(project, definitions):
    """Bulk-create endpoint definitions, skipping duplicate routes."""
    existing = {
        (e.method, e.path)
        for e in project.endpoints.only("method", "path")
    }
    created = []
    for definition in definitions:
        if (definition["method"], definition["path"]) in existing:
            continue
        endpoint = Endpoint.objects.create(project=project, **definition)
        seed_resource(endpoint)
        created.append(endpoint)
    return created


class ImportOpenApiView(OwnedProjectMixin, APIView):
    """Create endpoints from an OpenAPI 3.x spec (YAML or JSON)."""

    def post(self, request, project_pk):
        project = self.project
        spec = str(request.data.get("spec", ""))
        if not spec.strip():
            return Response(
                {"spec": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            definitions = parse_openapi(spec)
        except ValueError as exc:
            return Response(
                {"spec": [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        created = create_endpoints(project, definitions)
        serializer = EndpointSerializer(created, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PublicDocsView(APIView):
    """Read-only, unauthenticated docs for a project's mock API.

    Exposes only what a consumer needs: endpoint shapes and
    examples. Never logs, owner info, or resource state.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        project = generics.get_object_or_404(Project, slug=slug)
        endpoints = EndpointSerializer(
            project.endpoints.all(), many=True
        ).data
        return Response(
            {
                "name": project.name,
                "slug": project.slug,
                "endpoints": endpoints,
            }
        )


class AiProgressView(OwnedProjectMixin, APIView):
    """Live progress of the current AI generation for a project."""

    def get(self, request, project_pk):
        self.project.refresh_from_db(fields=["ai_progress"])
        return Response(self.project.ai_progress or {})


class RequestLogListView(OwnedProjectMixin, generics.ListAPIView):
    serializer_class = RequestLogSerializer

    def get_queryset(self):
        return RequestLog.objects.filter(project=self.project)[:200]
