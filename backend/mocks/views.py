from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .ai import AiUnavailable, generate_endpoints
from .models import Endpoint, Project, RequestLog
from .serializers import (
    EndpointSerializer,
    ProjectSerializer,
    RegisterSerializer,
    RequestLogSerializer,
)


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
        serializer.save(project=self.project)


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

        existing = {
            (e.method, e.path)
            for e in project.endpoints.only("method", "path")
        }
        created = [
            Endpoint.objects.create(project=project, **definition)
            for definition in definitions
            if (definition["method"], definition["path"]) not in existing
        ]
        serializer = EndpointSerializer(created, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RequestLogListView(OwnedProjectMixin, generics.ListAPIView):
    serializer_class = RequestLogSerializer

    def get_queryset(self):
        return RequestLog.objects.filter(project=self.project)[:200]
