from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from mocks.mock_server import MockServerView
from mocks.streaming import log_stream
from mocks.views import (
    AiGenerateView,
    AiProgressView,
    ImportOpenApiView,
    PublicDocsView,
    EndpointViewSet,
    ProjectViewSet,
    RegisterView,
    RequestLogListView,
    ResourceListView,
    ResourceResetView,
)

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")

endpoint_list = EndpointViewSet.as_view({"get": "list", "post": "create"})
endpoint_detail = EndpointViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/register/", RegisterView.as_view()),
    path("api/auth/token/", TokenObtainPairView.as_view()),
    path("api/auth/token/refresh/", TokenRefreshView.as_view()),
    path("api/", include(router.urls)),
    path(
        "api/projects/<int:project_pk>/endpoints/",
        endpoint_list,
    ),
    path(
        "api/projects/<int:project_pk>/endpoints/<int:pk>/",
        endpoint_detail,
    ),
    path(
        "api/projects/<int:project_pk>/resources/",
        ResourceListView.as_view(),
    ),
    path(
        "api/projects/<int:project_pk>/resources/<int:pk>/reset/",
        ResourceResetView.as_view(),
    ),
    path(
        "api/projects/<int:project_pk>/generate/",
        AiGenerateView.as_view(),
    ),
    path(
        "api/projects/<int:project_pk>/generate/progress/",
        AiProgressView.as_view(),
    ),
    path(
        "api/projects/<int:project_pk>/import-openapi/",
        ImportOpenApiView.as_view(),
    ),
    path(
        "api/projects/<int:project_pk>/logs/",
        RequestLogListView.as_view(),
    ),
    path(
        "api/projects/<int:project_pk>/logs/stream/",
        log_stream,
    ),
    path("api/docs/<slug:slug>/", PublicDocsView.as_view()),
    path("m/<slug:slug>/", MockServerView.as_view()),
    path("m/<slug:slug>/<path:mock_path>", MockServerView.as_view()),
]
