"""Open CORS for the mock endpoints themselves.

The dashboard API stays restricted to the app's own origins
(django-cors-headers), but /m/... mock URLs and the public docs API
exist to be called from the user's own apps — any origin, any method,
any headers. This middleware answers preflights directly and stamps
permissive CORS headers on every mock response.
"""

from django.http import HttpResponse

OPEN_CORS_PREFIXES = ("/m/", "/api/docs/")


class MockCorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(OPEN_CORS_PREFIXES):
            return self.get_response(request)

        # Real preflight: answer here so it never 404s against the
        # user's defined endpoints (mocks only define real methods)
        if (
            request.method == "OPTIONS"
            and request.headers.get("Access-Control-Request-Method")
        ):
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        )
        response["Access-Control-Allow-Headers"] = request.headers.get(
            "Access-Control-Request-Headers", "*"
        ) or "*"
        response["Access-Control-Max-Age"] = "86400"
        response["Access-Control-Expose-Headers"] = "*"
        return response
