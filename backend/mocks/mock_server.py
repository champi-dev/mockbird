"""The catch-all view that serves live mock endpoints."""

import random
import time

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import Endpoint, Project, RequestLog

MAX_DELAY_MS = 30_000


@method_decorator(csrf_exempt, name="dispatch")
class MockServerView(View):
    """Resolves /m/<slug>/<any/path> against stored Endpoint rows."""

    def dispatch(self, request, slug, mock_path=""):
        project = Project.objects.filter(slug=slug).first()
        if project is None:
            return JsonResponse(
                {"error": "Unknown mock project."}, status=404
            )

        path = "/" + mock_path
        endpoint = Endpoint.objects.filter(
            project=project, method=request.method, path=path
        ).first()

        if endpoint is None:
            response = JsonResponse(
                {"error": f"No mock for {request.method} {path}."},
                status=404,
            )
            self._log(project, request, path, 404, matched=False)
            return response

        self._apply_delay(endpoint)
        status = self._resolve_status(endpoint)
        response = JsonResponse(
            endpoint.response_body, status=status, safe=False
        )
        for key, value in endpoint.headers.items():
            response[key] = value

        self._log(project, request, path, status, matched=True)
        return response

    @staticmethod
    def _apply_delay(endpoint):
        delay = min(endpoint.delay_ms, MAX_DELAY_MS)
        if delay:
            time.sleep(delay / 1000)

    @staticmethod
    def _resolve_status(endpoint):
        if random.randint(1, 100) <= endpoint.error_rate:
            return endpoint.error_status
        return endpoint.status_code

    @staticmethod
    def _log(project, request, path, status, matched):
        RequestLog.objects.create(
            project=project,
            method=request.method,
            path=path,
            body=request.body[:10_000].decode("utf-8", errors="replace"),
            status_code=status,
            matched=matched,
        )
