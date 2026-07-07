"""Turn a natural-language API description into endpoint definitions
using OpenAI (gpt-4o-mini, JSON mode)."""

import json

import requests
from django.conf import settings

from .models import HTTP_METHODS

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"
VALID_METHODS = {m for m, _ in HTTP_METHODS}

SYSTEM_PROMPT = """\
You design mock REST APIs. Given a description of an API, output the
endpoints it should have, with realistic example JSON responses.

FIRST invent one small consistent dataset for the domain (e.g. 3
products with ids 1-3), THEN derive every endpoint from that SAME
dataset so endpoints relate to each other: the list endpoint returns
exactly those records, detail endpoints like /products/1 return the
matching record, a POST returns a plausible newly-created record
(next id), DELETE returns 204 or a confirmation referencing a real
id. Never use unrelated placeholder data.

Reply ONLY with JSON of this shape:
{"endpoints": [
  {"method": "GET", "path": "/things",
   "description": "one line: what this does and expected inputs",
   "request_example": {"query_params": {"page": 1},
                       "body": {"name": "..."}},
   "status_code": 200,
   "response_body": <realistic example JSON from the dataset>,
   "headers": {}, "delay_ms": 0}
]}

Rules: 3-8 endpoints; methods limited to GET/POST/PUT/PATCH/DELETE;
paths are concrete (use real ids from your dataset like /things/1,
no {id} placeholders); request_example documents the query params
and/or body a caller should send (omit keys that don't apply, use
{} when none); descriptions are short and concrete."""


class AiUnavailable(Exception):
    """AI generation cannot be performed right now."""


def generate_endpoints(description: str) -> list[dict]:
    """Call OpenAI and return a sanitized list of endpoint dicts."""
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise AiUnavailable("OPENAI_API_KEY is not configured.")

    try:
        resp = requests.post(
            OPENAI_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": MODEL,
                "temperature": 0.4,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": description[:2000]},
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        payload = json.loads(content)
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise AiUnavailable(f"AI request failed: {exc}") from exc

    return parse_endpoints(payload)


def parse_endpoints(payload: dict) -> list[dict]:
    """Validate and clamp model output; drop anything malformed."""
    result = []
    for item in payload.get("endpoints", []):
        if not isinstance(item, dict):
            continue
        method = str(item.get("method", "")).upper()
        path = str(item.get("path", "")).strip()
        if method not in VALID_METHODS or not path:
            continue
        if not path.startswith("/"):
            path = "/" + path
        result.append(
            {
                "method": method,
                "path": path[:255],
                "description": str(item.get("description", ""))[:255],
                "request_example": (
                    item.get("request_example")
                    if isinstance(item.get("request_example"), dict)
                    else {}
                ),
                "status_code": _clamp(item.get("status_code"), 100, 599, 200),
                "response_body": item.get("response_body", {}),
                "headers": item.get("headers") or {},
                "delay_ms": _clamp(item.get("delay_ms"), 0, 30000, 0),
            }
        )
    return result[:10]


def _clamp(value, low, high, default):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return default if not low <= value <= high else value
