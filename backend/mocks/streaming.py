"""Server-sent events stream of a project's request log.

EventSource cannot send an Authorization header, so the JWT access
token is passed as a `?token=` query param and validated manually.
"""

import json
import time

from django.http import HttpResponse, StreamingHttpResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import (
    AuthenticationFailed,
    InvalidToken,
)

from .models import Project, RequestLog
from .serializers import RequestLogSerializer

POLL_SECONDS = 2
MAX_LIFETIME_SECONDS = 300


def iter_log_events(project, last_id, max_seconds=MAX_LIFETIME_SECONDS):
    """Yield SSE frames for logs newer than last_id until timeout."""
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        fresh = RequestLog.objects.filter(
            project=project, id__gt=last_id
        ).order_by("id")
        for log in fresh:
            last_id = log.id
            data = json.dumps(RequestLogSerializer(log).data)
            yield f"data: {data}\n\n"
        yield ": keepalive\n\n"
        time.sleep(POLL_SECONDS)


def _user_from_token(raw_token):
    auth = JWTAuthentication()
    validated = auth.get_validated_token(raw_token)
    return auth.get_user(validated)


def log_stream(request, project_pk):
    try:
        user = _user_from_token(request.GET.get("token", ""))
    except (InvalidToken, AuthenticationFailed):
        return HttpResponse(status=401)

    project = Project.objects.filter(owner=user, pk=project_pk).first()
    if project is None:
        return HttpResponse(status=404)

    latest = (
        RequestLog.objects.filter(project=project)
        .order_by("-id")
        .values_list("id", flat=True)
        .first()
    ) or 0

    response = StreamingHttpResponse(
        iter_log_events(project, latest),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
