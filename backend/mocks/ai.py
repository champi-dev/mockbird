"""Turn a natural-language API description into endpoint definitions
using any OpenAI-compatible chat completions API (JSON mode).

Configured via settings.AI_BASE_URL / AI_MODEL / AI_API_KEY — defaults to
a local Ollama running qwen3:1.7b; works unchanged against OpenAI."""

import json
import re

import requests
from django.conf import settings

from .models import HTTP_METHODS

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

Prefer STATEFUL endpoints for the main resources: set
"mode": "stateful" and "resource": "<plural-resource-name>", use
"{id}" as the path parameter (e.g. /things/{id}), and give the list
endpoint (GET collection) the dataset as its response_body — it seeds
the live state. Stateful endpoints then really work: POST inserts,
PATCH merges, DELETE removes, GET reads current state. Use
"mode": "static" only for routes that aren't collection CRUD (e.g.
/health, reports); static paths may also use {id} and reference it
in the body as "{{params.id}}".

Reply ONLY with JSON of this shape:
{"endpoints": [
  {"method": "GET", "path": "/things",
   "mode": "stateful", "resource": "things",
   "description": "one line: what this does and expected inputs",
   "request_example": {"query_params": {"page": 1},
                       "body": {"name": "..."}},
   "status_code": 200,
   "response_body": <the dataset / realistic example JSON>,
   "headers": {}, "delay_ms": 0}
]}

Rules: 3-8 endpoints; methods limited to GET/POST/PUT/PATCH/DELETE;
every dict in the dataset has an integer "id"; request_example
documents the query params and/or body a caller should send (omit
keys that don't apply, use {} when none); descriptions are short
and concrete."""


class AiUnavailable(Exception):
    """AI generation cannot be performed right now."""


def generate_endpoints(description: str) -> list[dict]:
    """Call the configured model and return sanitized endpoint dicts."""
    base_url = getattr(settings, "AI_BASE_URL", "").rstrip("/")
    model = getattr(settings, "AI_MODEL", "")
    if not base_url or not model:
        raise AiUnavailable("AI_BASE_URL / AI_MODEL are not configured.")

    # Local runtimes (Ollama) ignore auth; hosted APIs need a real key
    api_key = getattr(settings, "AI_API_KEY", "") or "unused"

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": 0.4,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": description[:2000]},
                ],
            },
            timeout=120,  # local small models can be slow on cold start
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        payload = json.loads(_extract_json(content))
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise AiUnavailable(f"AI request failed: {exc}") from exc

    return parse_endpoints(payload)


def _extract_json(content: str) -> str:
    """Tolerate reasoning-model output: strip <think> blocks and code
    fences, then cut to the outermost JSON object."""
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    content = re.sub(r"```(?:json)?|```", "", content)
    start, end = content.find("{"), content.rfind("}")
    if start != -1 and end > start:
        return content[start : end + 1]
    return content.strip()


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
                "mode": (
                    "stateful"
                    if item.get("mode") == "stateful"
                    and item.get("resource")
                    else "static"
                ),
                "resource": str(item.get("resource", ""))[:64],
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
