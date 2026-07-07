"""Convert an OpenAPI 3.x spec (YAML or JSON text) into Mockbird
endpoint definitions.

OpenAPI path templating (`/pets/{petId}`) matches Mockbird's own
`{param}` syntax, so paths pass through unchanged.
"""

import yaml

from .models import HTTP_METHODS

VALID_METHODS = {m for m, _ in HTTP_METHODS}
DEFAULT_STATUS = {"post": 201, "delete": 204}


def parse_openapi(text: str) -> list[dict]:
    """Return endpoint definition dicts; raise ValueError if bad."""
    try:
        spec = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Not valid YAML/JSON: {exc}") from exc

    if not isinstance(spec, dict) or "paths" not in spec:
        raise ValueError("Spec has no 'paths' section.")

    endpoints = []
    for path, operations in spec["paths"].items():
        if not isinstance(operations, dict):
            continue
        for verb, op in operations.items():
            method = verb.upper()
            if method not in VALID_METHODS or not isinstance(op, dict):
                continue
            status, body = _pick_response(op, verb)
            endpoints.append(
                {
                    "method": method,
                    "path": str(path)[:255],
                    "description": str(
                        op.get("summary") or op.get("description") or ""
                    )[:255],
                    "request_example": _request_example(op),
                    "status_code": status,
                    "response_body": body,
                }
            )
    return endpoints


def _pick_response(op, verb):
    """Choose the best (status, example body) from an operation."""
    responses = op.get("responses") or {}
    for code in sorted(responses):
        if str(code).startswith("2"):
            status = int(code)
            content = (responses[code] or {}).get("content") or {}
            media = content.get("application/json") or next(
                iter(content.values()), {}
            )
            return status, _example_from_media(media or {})
    return DEFAULT_STATUS.get(verb, 200), {}


def _example_from_media(media):
    if "example" in media:
        return media["example"]
    examples = media.get("examples") or {}
    for entry in examples.values():
        if isinstance(entry, dict) and "value" in entry:
            return entry["value"]
    return _example_from_schema(media.get("schema") or {})


def _example_from_schema(schema, depth=0):
    """Synthesize a plausible example from a JSON schema."""
    if depth > 5 or not isinstance(schema, dict):
        return {}
    if "example" in schema:
        return schema["example"]
    kind = schema.get("type")
    if kind == "object" or "properties" in schema:
        return {
            name: _example_from_schema(sub, depth + 1)
            for name, sub in (schema.get("properties") or {}).items()
        }
    if kind == "array":
        return [_example_from_schema(schema.get("items") or {}, depth + 1)]
    return {
        "string": "string",
        "integer": 0,
        "number": 0.0,
        "boolean": True,
    }.get(kind, {})


def _request_example(op):
    example = {}
    query = {}
    for param in op.get("parameters") or []:
        if isinstance(param, dict) and param.get("in") == "query":
            schema = param.get("schema") or {}
            query[param.get("name", "?")] = schema.get(
                "example", _example_from_schema(schema)
            )
    if query:
        example["query_params"] = query

    content = ((op.get("requestBody") or {}).get("content")) or {}
    media = content.get("application/json") or next(
        iter(content.values()), None
    )
    if media:
        example["body"] = _example_from_media(media)
    return example
