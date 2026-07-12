"""Stateful CRUD behaviour for mock endpoints backed by a Resource.

The operation is derived from the HTTP method and whether the path
captured an `{id}`-style param (any single captured param is treated
as the item id, matched against each item's "id" field).
"""

import json

from .models import Resource


def handle_stateful(endpoint, params, body_bytes):
    """Return (status_code, data|None) after applying the operation."""
    resource, _ = Resource.objects.get_or_create(
        project=endpoint.project, name=endpoint.resource
    )
    # Whatever the user named their param ({id}, {petId}...), the
    # first captured value is treated as the item id.
    item_id = next(iter(params.values()), None)
    payload = _parse_body(body_bytes)
    method = endpoint.method

    if method == "GET":
        if item_id is None:
            return 200, resource.items
        item = _find(resource.items, item_id)
        return (200, item) if item else (404, _missing(item_id))

    if method == "POST":
        item = {"id": _next_id(resource.items), **payload}
        resource.items = resource.items + [item]
        resource.save(update_fields=["items"])
        return 201, item

    if method in ("PUT", "PATCH"):
        item = _find(resource.items, item_id)
        if not item:
            return 404, _missing(item_id)
        updated = (
            {**item, **payload}
            if method == "PATCH"
            else {"id": item["id"], **payload}
        )
        # Identity (`is`) picks exactly the matched dict even when two
        # items are equal by value; rebuilding the list (instead of
        # mutating in place) guarantees Django sees the JSONField as
        # changed and persists it.
        resource.items = [
            updated if i is item else i for i in resource.items
        ]
        resource.save(update_fields=["items"])
        return 200, updated

    if method == "DELETE":
        item = _find(resource.items, item_id)
        if not item:
            return 404, _missing(item_id)
        resource.items = [i for i in resource.items if i is not item]
        resource.save(update_fields=["items"])
        return 204, None

    return 405, {"error": f"Method {method} not supported."}


def _parse_body(body_bytes):
    try:
        data = json.loads(body_bytes or b"{}")
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def _find(items, item_id):
    for item in items:
        if isinstance(item, dict) and str(item.get("id")) == str(item_id):
            return item
    return None


def _next_id(items):
    ids = [
        item["id"]
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), int)
    ]
    return max(ids, default=0) + 1


def _missing(item_id):
    return {"error": f"Item {item_id} not found."}
