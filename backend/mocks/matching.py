"""Route matching for the mock server: exact paths first, then
`{param}` patterns, capturing path parameters."""

from .models import Endpoint


def find_endpoint(project, method, path):
    """Return (endpoint, params) for the best match, or (None, {})."""
    exact = Endpoint.objects.filter(
        project=project, method=method, path=path
    ).first()
    if exact:
        return exact, {}

    # Exact routes always beat patterns (/products/special wins over
    # /products/{id}); among patterns, first match in creation order.
    candidates = Endpoint.objects.filter(
        project=project, method=method, path__contains="{"
    )
    segments = _split(path)
    for endpoint in candidates:
        params = _match(_split(endpoint.path), segments)
        if params is not None:
            return endpoint, params
    return None, {}


def _split(path):
    return [s for s in path.split("/") if s]


def _match(pattern, actual):
    """Match segment lists; return captured params dict or None."""
    if len(pattern) != len(actual):
        return None
    params = {}
    for pat, seg in zip(pattern, actual):
        if pat.startswith("{") and pat.endswith("}"):
            params[pat[1:-1]] = seg
        elif pat != seg:
            return None
    return params


def render_template(value, params):
    """Recursively replace "{{params.x}}" placeholders in a JSON-like
    structure with captured path-parameter values."""
    if isinstance(value, str):
        for key, replacement in params.items():
            value = value.replace(f"{{{{params.{key}}}}}", replacement)
        return value
    if isinstance(value, list):
        return [render_template(v, params) for v in value]
    if isinstance(value, dict):
        return {k: render_template(v, params) for k, v in value.items()}
    return value
