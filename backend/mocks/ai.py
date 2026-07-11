"""Turn a natural-language API description into endpoint definitions
using any OpenAI-compatible chat completions API (JSON mode).

Configured via settings.AI_BASE_URL / AI_MODEL / AI_API_KEY — defaults to
a local Ollama running qwen3:1.7b; works unchanged against OpenAI."""

import json
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings

from .models import HTTP_METHODS

VALID_METHODS = {m for m, _ in HTTP_METHODS}

PLAN_PROMPT = """\
Extract the data resources for a mock REST API from the user's
description. Rules:
- Use the user's own words: plural, lowercase, snake_case names.
- Include EVERY resource the user mentions, also junction/linking
  resources that connect two others. 1-5 resources total.
- For each resource give "fields": one realistic example record —
  always an integer "id", the fields the user asked for (or sensible
  ones), and <other>_id integer fields when it references another
  resource (e.g. a loan has book_id and member_id).
- REQUIRED: if the description says X contain/have/belong to Y (e.g.
  "projects contain tasks"), then resource Y's fields MUST include
  the integer field <x_singular>_id linking it to its parent.
- "actions": which of ["create","update","delete"] make sense.

Reply ONLY with JSON in this shape (the values are placeholders —
never copy them, derive everything from the user's description):
{"resources": [{"name": "<plural_resource_name>",
  "fields": {"id": 1, "<field>": "<example value>"},
  "actions": ["create","update","delete"]}]}"""

RECORDS_PROMPT = """\
Create 3-4 realistic example records for the resource "{name}" of this
API: {description}

Each record has exactly these fields: {fields} — an integer "id"
(1, 2, 3...) and realistic, mutually consistent values. Fields ending
in _id reference ids 1-3 of that other resource.

Reply ONLY with JSON: {{"records": [...]}}"""


class AiUnavailable(Exception):
    """AI generation cannot be performed right now."""


def generate_endpoints(description: str, progress=None, log=None) -> list[dict]:
    """Two-stage generation tuned for small local models:

    1. The model extracts a resource plan (names, fields, actions) —
       a short, reliable task.
    2. The model writes realistic records per resource.
    3. The CRUD endpoint skeleton is assembled deterministically in
       code, so structure, statefulness and seeding are guaranteed.
    """
    def report(percent, text):
        if progress:
            progress(percent, text)

    report(5, "Analyzing your description…")
    plan = _plan_resources(description, log)[:5]
    names = ", ".join(r["name"] for r in plan)
    report(30, f"Designed {len(plan)} resource{'s' if len(plan) != 1 else ''}: {names}. Creating realistic data…")

    done = 0
    def gen(res):
        nonlocal done
        records = _gen_records(description, res, log)
        done += 1
        pct = 30 + int(55 * done / max(len(plan), 1))
        report(pct, f"Created data for '{res['name']}' ({done}/{len(plan)})…")
        return records

    with ThreadPoolExecutor(max_workers=3) as pool:
        record_sets = list(pool.map(gen, plan))

    report(90, "Assembling endpoints…")
    endpoints: list[dict] = []
    for res, records in zip(plan, record_sets):
        endpoints.extend(_crud_endpoints(res, records))
    return endpoints[:20]


def _plan_resources(description: str, log=None) -> list[dict]:
    last_error = None
    for attempt in range(4):
        try:
            payload = _call_model(
                PLAN_PROMPT, description[:2000], attempt,
                on_token=_writer(log, "resource plan", attempt),
            )
        except AiUnavailable as exc:
            last_error = exc
            continue
        resources = []
        for r in payload.get("resources", []):
            name = _slugify(r.get("name")) if isinstance(r, dict) else ""
            fields = r.get("fields") if isinstance(r, dict) else None
            if not name or not isinstance(fields, dict) or not fields:
                continue
            actions = r.get("actions")
            if not isinstance(actions, list):
                actions = ["create", "update", "delete"]
            resources.append(
                {"name": name, "fields": fields, "actions": actions}
            )
        resources = [
            r for r in resources
            if r["name"] not in FORBIDDEN_NAMES
        ]
        if resources:
            return _link_parents(description, resources)
    raise last_error or AiUnavailable("Could not derive resources.")


FORBIDDEN_NAMES = {
    "things", "thing", "resources", "resource", "items",
    "plural_resource_name", "examples", "objects", "records",
}


def _singular(name: str) -> str:
    if name.endswith("ies"):
        return name[:-3] + "y"
    return name[:-1] if name.endswith("s") else name


def _link_parents(description: str, resources: list[dict]) -> list[dict]:
    """Deterministic containment links: drop nonsense self-links and,
    when the description says "X contain/have Y", make sure resource Y
    carries an <x_singular>_id field — small models often miss it."""
    desc = description.lower()
    names = {r["name"] for r in resources}
    for r in resources:
        own = _singular(r["name"])
        r["fields"].pop(f"{own}_id", None)
        r["fields"].pop(f"{r['name']}_id", None)
    stop = {"i", "we", "you", "they", "it", "that", "which", "must",
            "also", "can", "should", "each", "every", "all", "the",
            "a", "an", "to", "and", "api", "app", "endpoints"}
    for r in resources:
        child = _singular(r["name"])
        match = re.search(
            rf"([a-z_]+?)s?\s+"
            rf"(?:contains?|have|has|holds?|owns?)\s+"
            rf"(?:[a-z_]+\s+){{0,2}}{re.escape(child)}",
            desc,
        )
        if match:
            parent = _singular(match.group(1))
            if parent and parent != child and parent not in stop:
                r["fields"].setdefault(f"{parent}_id", 1)
    return resources


def _gen_records(description: str, res: dict, log=None) -> list[dict]:
    prompt = RECORDS_PROMPT.format(
        name=res["name"],
        description=description[:1500],
        fields=json.dumps(sorted(res["fields"].keys())),
    )
    for attempt in range(2):
        try:
            payload = _call_model(
                prompt, description[:1500], attempt,
                on_token=_writer(log, res["name"], attempt),
            )
        except AiUnavailable:
            continue
        records = [
            r for r in payload.get("records", []) if isinstance(r, dict)
        ]
        if records:
            return _ensure_ids(records[:5])
    # Fallback: the plan's example record still seeds working state
    return _ensure_ids([dict(res["fields"])])


def _crud_endpoints(res: dict, records: list[dict]) -> list[dict]:
    """Deterministic stateful CRUD family for one resource."""
    name, actions = res["name"], res["actions"]
    sample = records[0] if records else {"id": 1}
    body_example = {k: v for k, v in sample.items() if k != "id"}
    created = {"id": max(r["id"] for r in records) + 1, **body_example}

    def ep(method, path, desc, status, body, req=None):
        return {
            "method": method, "path": path, "mode": "stateful",
            "resource": name, "description": desc,
            "request_example": req or {}, "status_code": status,
            "response_body": body, "headers": {}, "delay_ms": 0,
        }

    endpoints = [
        ep("GET", f"/{name}", f"List all {name}.", 200, records),
        ep("GET", f"/{name}/{{id}}", f"Get one of the {name} by id.",
           200, sample),
    ]
    if "create" in actions:
        endpoints.append(
            ep("POST", f"/{name}", f"Create a new item in {name}.",
               201, created, {"body": body_example})
        )
    if "update" in actions:
        endpoints.append(
            ep("PATCH", f"/{name}/{{id}}",
               f"Update fields of one of the {name}.",
               200, sample, {"body": body_example})
        )
    if "delete" in actions:
        endpoints.append(
            ep("DELETE", f"/{name}/{{id}}",
               f"Delete one of the {name} by id.", 204, {})
        )
    return endpoints


def _slugify(value) -> str:
    if not isinstance(value, str):
        return ""
    value = re.sub(r"[^a-z0-9_]+", "_", value.strip().lower())
    return value.strip("_")[:64]


def _writer(log, label, attempt):
    """Token callback for one model call, or None when not logging."""
    if not log:
        return None
    if attempt:
        log(label, f"\n[attempt {attempt + 1}]\n")
    return lambda fragment: log(label, fragment)


def _call_model(
    system_prompt: str, user_content: str, attempt: int, on_token=None
) -> dict:
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
                # near-deterministic; retries get a little diversity
                "temperature": 0.0 + 0.3 * attempt,
                "response_format": {"type": "json_object"},
                "max_tokens": 3000,
                "stream": True,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    # /no_think: qwen3 soft switch — without it the model
                    # can spend the whole token budget on reasoning and
                    # return empty content
                    {"role": "user", "content": user_content + " /no_think"},
                ],
            },
            timeout=60,  # per attempt; gunicorn worker timeout is 300s
            stream=True,
        )
        resp.raise_for_status()
        # OpenAI-style SSE stream: forward each content delta to the
        # live log so users can watch the model work
        parts: list[str] = []
        for line in resp.iter_lines():
            if not line or not line.startswith(b"data: "):
                continue
            data = line[6:]
            if data.strip() == b"[DONE]":
                break
            try:
                delta = json.loads(data)["choices"][0]["delta"]
            except (ValueError, KeyError, IndexError):
                continue
            fragment = delta.get("content") or ""
            if fragment:
                parts.append(fragment)
                if on_token:
                    on_token(fragment)
        content = "".join(parts)
        return json.loads(_extract_json(content))
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise AiUnavailable(f"AI request failed: {exc}") from exc


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


def normalize_endpoints(endpoints: list[dict]) -> list[dict]:
    """Deterministically repair the sloppiness small local models
    produce, so generated APIs are always coherent and stateful:

    - literal numeric ids in paths -> {id}
    - duplicate (method, path) endpoints dropped
    - endpoints of a stateful resource forced to stateful mode
    - list endpoint's dataset unwrapped when nested in an object
    - dataset items get sequential integer ids when missing
    - a missing list GET is synthesized so state always seeds
    """
    _infer_stateful_families(endpoints)

    stateful_resources = {
        e["resource"] for e in endpoints if e["mode"] == "stateful"
    }

    seen, result = set(), []
    for e in endpoints:
        # A resource that is stateful anywhere is stateful everywhere
        if e["resource"] in stateful_resources:
            e["mode"] = "stateful"
        if e["mode"] == "stateful":
            e["path"] = re.sub(r"/\d+(?=/|$)", "/{id}", e["path"])
        key = (e["method"], e["path"])
        if key in seen:
            continue
        seen.add(key)
        result.append(e)

    for res in sorted(stateful_resources):
        res_eps = [e for e in result if e["resource"] == res]
        list_eps = [
            e for e in res_eps
            if e["method"] == "GET" and "{" not in e["path"]
        ]

        dataset = None
        for e in list_eps + res_eps:
            candidate = _as_dataset(e["response_body"])
            if candidate:
                dataset = candidate
                break
        if dataset is None:
            # Last resort: derive one record from any dict body
            for e in res_eps:
                if isinstance(e["response_body"], dict) and e["response_body"]:
                    dataset = [e["response_body"]]
                    break
        dataset = _ensure_ids(dataset or [])

        if list_eps:
            list_eps[0]["response_body"] = dataset
        else:
            base = "/" + res
            for e in res_eps:  # reuse the family's base path if visible
                if "{" in e["path"]:
                    base = e["path"].split("/{")[0] or base
                    break
                base = e["path"]
            result.append(
                {
                    "method": "GET",
                    "path": base,
                    "mode": "stateful",
                    "resource": res,
                    "description": f"List all {res}.",
                    "request_example": {},
                    "status_code": 200,
                    "response_body": dataset,
                    "headers": {},
                    "delay_ms": 0,
                }
            )

    return result[:12]


def _infer_stateful_families(endpoints: list[dict]) -> None:
    """Models sometimes emit an obvious CRUD family as static with no
    resource. If several endpoints share a base collection path and the
    bare GET carries a dataset, treat the family as stateful."""
    families: dict[str, list[dict]] = {}
    for e in endpoints:
        if e["mode"] == "stateful" or e["resource"]:
            continue
        base = e["path"].strip("/").split("/")[0]
        if base:
            families.setdefault(base, []).append(e)

    for base, group in families.items():
        if len(group) < 2:
            continue  # a lone /health-style route stays static
        list_gets = [
            e for e in group
            if e["method"] == "GET" and "{" not in e["path"]
            and e["path"].strip("/") == base
        ]
        if list_gets and _as_dataset(list_gets[0]["response_body"]):
            for e in group:
                e["mode"] = "stateful"
                e["resource"] = base


def _as_dataset(body) -> list | None:
    """Return the record list inside body, unwrapping one dict level
    (e.g. {"books": [...]} -> [...]); None when there isn't one."""
    if isinstance(body, list) and body and all(
        isinstance(i, dict) for i in body
    ):
        return body
    if isinstance(body, dict):
        lists = [
            v for v in body.values()
            if isinstance(v, list) and v and all(isinstance(i, dict) for i in v)
        ]
        if lists:
            return max(lists, key=len)
    return None


def _ensure_ids(items: list) -> list:
    """Give every record a UNIQUE integer id (duplicates included —
    small models repeat ids, which breaks id-based CRUD)."""
    valid = [
        i["id"] for i in items
        if isinstance(i, dict) and isinstance(i.get("id"), int)
    ]
    next_id = max(valid, default=0) + 1
    used: set[int] = set()
    fixed = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if not isinstance(item_id, int) or item_id in used:
            item_id = next_id
            next_id += 1
        used.add(item_id)
        fixed.append({"id": item_id, **{k: v for k, v in item.items() if k != "id"}})
    return fixed


def _clamp(value, low, high, default):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return default if not low <= value <= high else value
