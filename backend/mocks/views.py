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
        project = self.project
        description = str(request.data.get("description", "")).strip()
        if not description:
            return Response(
                {"description": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            definitions = generate_endpoints(description)
        except AiUnavailable as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        created = create_endpoints(project, definitions)
        serializer = EndpointSerializer(created, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


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


class RequestLogListView(OwnedProjectMixin, generics.ListAPIView):
    serializer_class = RequestLogSerializer

    def get_queryset(self):
        return RequestLog.objects.filter(project=self.project)[:200]
