from rest_framework import generics, permissions, viewsets

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


class RequestLogListView(OwnedProjectMixin, generics.ListAPIView):
    serializer_class = RequestLogSerializer

    def get_queryset(self):
        return RequestLog.objects.filter(project=self.project)[:200]
