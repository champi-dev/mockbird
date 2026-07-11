#!/usr/bin/env python3
"""Mockbird AI-generation eval: vague -> detailed descriptions.
Creates a project per case, generates endpoints, asserts structure,
then exercises the LIVE mock (seeded state + CRUD coherence)."""
import json, sys, time
import requests

BASE = "http://127.0.0.1:8097"
USER, PW = "evalbot", "Ev4lB0t!2026"

CASES = [
    # (id, description, expected keywords in resources/paths)
    ("vague-todo", "a todo app", ["todo", "task"]),
    ("vague-gym", "something for my gym", ["member", "class", "workout", "gym", "trainer"]),
    ("vague-pets", "pets", ["pet", "dog", "cat", "animal"]),
    ("med-blog", "a blog with posts and comments", ["post", "comment"]),
    ("med-shop", "inventory for a small shop with products and categories", ["product", "categor"]),
    ("med-movies", "movie watchlist api where i can rate movies", ["movie", "watch", "rating", "rate"]),
    ("det-library", "A library API: books (title, author, isbn, available), members (name, email, joined_at), and loans linking a book and member with a due_date. I need to list/search books, register members, create a loan (borrow) and delete a loan (return).", ["book", "member", "loan"]),
    ("det-tasks", "task manager: projects contain tasks; a task has title, status (todo/doing/done) and assignee. endpoints: list tasks of a project, create a task, update task status, delete a task", ["task", "project"]),
    ("det-restaurant", "restaurant reservations: tables (number, seats) and reservations (customer_name, party_size, time, table_id). list tables, list reservations, create a reservation, cancel a reservation", ["table", "reservation"]),
    ("det-ecommerce", "e-commerce backend with products (name, price, stock), customers, and orders (customer_id, items, total, status pending/shipped/delivered). full CRUD on products, create orders, get order status", ["product", "customer", "order"]),
]

def auth():
    requests.post(f"{BASE}/api/auth/register/", json={"username": USER, "password": PW, "email": "e@e.co"})
    r = requests.post(f"{BASE}/api/auth/token/", json={"username": USER, "password": PW})
    return {"Authorization": f"Bearer {r.json()['access']}"}

def evaluate_case(H, cid, desc, keywords):
    r = requests.post(f"{BASE}/api/projects/", headers=H, json={"name": f"eval {cid}"})
    proj = r.json(); pid, slug = proj["id"], proj["slug"]
    t0 = time.time()
    r = requests.post(f"{BASE}/api/projects/{pid}/generate/", headers=H,
                      json={"description": desc}, timeout=30)
    issues, notes = [], []
    if r.status_code != 202:
        requests.delete(f"{BASE}/api/projects/{pid}/", headers=H)
        return {"case": cid, "ok": False, "issues": [f"start failed {r.status_code}: {r.text[:120]}"], "notes": [], "took": 0, "endpoints": []}
    state = ""
    while time.time() - t0 < 290:
        time.sleep(4)
        p = requests.get(f"{BASE}/api/projects/{pid}/generate/progress/", headers=H).json()
        state = p.get("status", "")
        if state in ("done", "error"):
            break
    took = time.time() - t0
    if state != "done":
        issues.append(f"GENERATION {state or 'timed out'}: {p.get('text','')[:120]}")
        requests.delete(f"{BASE}/api/projects/{pid}/", headers=H)
        return {"case": cid, "ok": False, "issues": issues, "notes": [], "took": took, "endpoints": []}
    eps = requests.get(f"{BASE}/api/projects/{pid}/endpoints/", headers=H).json()

    # --- structural ---
    if len(eps) < 3: issues.append(f"only {len(eps)} endpoints")
    seen = set()
    for e in eps:
        key = (e["method"], e["path"])
        if key in seen: issues.append(f"duplicate {key}")
        seen.add(key)
    stateful = [e for e in eps if e["mode"] == "stateful"]
    if not stateful: issues.append("no stateful endpoints at all")
    resources = {e["resource"] for e in stateful}

    # semantic: at least one keyword reflected in resources/paths
    blob = " ".join([e["path"] + " " + e["resource"] for e in eps]).lower()
    if not any(k in blob for k in keywords):
        issues.append(f"domain mismatch: none of {keywords} in {sorted(resources) or [e['path'] for e in eps]}")

    # per resource: list endpoint must exist and have seeded a non-empty state
    for res in sorted(resources):
        res_eps = [e for e in stateful if e["resource"] == res]
        list_eps = [e for e in res_eps if e["method"] == "GET" and "{" not in e["path"]]
        if not list_eps:
            issues.append(f"resource '{res}': no list GET"); continue
        list_path = list_eps[0]["path"].lstrip("/")
        # --- behavioral: live mock ---
        m = f"{BASE}/m/{slug}"
        r = requests.get(f"{m}/{list_path}")
        if r.status_code != 200:
            issues.append(f"'{res}': live list GET -> {r.status_code}"); continue
        data = r.json()
        if not isinstance(data, list) or not data:
            issues.append(f"'{res}': state NOT seeded (list returned {str(data)[:60]})"); continue
        if not all(isinstance(i, dict) and "id" in i for i in data):
            issues.append(f"'{res}': items missing ids"); continue
        notes.append(f"'{res}': seeded {len(data)} items, fields {sorted(data[0].keys())[:6]}")
        first_id = data[0]["id"]
        # detail GET
        detail = [e for e in res_eps if e["method"] == "GET" and "{" in e["path"]]
        if detail:
            dp = detail[0]["path"].lstrip("/").replace("{id}", str(first_id))
            dp = "/".join(p if not (p.startswith("{") and p.endswith("}")) else str(first_id) for p in dp.split("/"))
            r = requests.get(f"{m}/{dp}")
            if r.status_code != 200 or r.json().get("id") != first_id:
                issues.append(f"'{res}': detail GET incoherent ({r.status_code})")
        # POST -> appears in list
        post = [e for e in res_eps if e["method"] == "POST"]
        if post:
            sample = {k: v for k, v in data[0].items() if k != "id"}
            r = requests.post(f"{m}/{post[0]['path'].lstrip('/')}", json=sample)
            if r.status_code != 201:
                issues.append(f"'{res}': POST -> {r.status_code}")
            else:
                new_id = r.json().get("id")
                now = requests.get(f"{m}/{list_path}").json()
                if not any(i.get("id") == new_id for i in now):
                    issues.append(f"'{res}': POSTed item not in state")
                else:
                    notes.append(f"'{res}': POST->id {new_id} persisted")
        # DELETE removes
        dele = [e for e in res_eps if e["method"] == "DELETE" and "{" in e["path"]]
        if dele:
            dp = "/".join(p if not (p.startswith("{") and p.endswith("}")) else str(first_id) for p in dele[0]["path"].lstrip("/").split("/"))
            r = requests.delete(f"{m}/{dp}")
            if r.status_code not in (200, 204):
                issues.append(f"'{res}': DELETE -> {r.status_code}")
            elif any(i.get("id") == first_id for i in requests.get(f"{m}/{list_path}").json()):
                issues.append(f"'{res}': DELETEd item still in state")
            else:
                notes.append(f"'{res}': DELETE persisted")

    # detailed cases: every explicitly demanded resource must exist as state
    REQUIRED = {"det-library": ["book", "loan"], "det-restaurant": ["table", "reservation"],
                "det-ecommerce": ["product", "order"], "det-tasks": ["task"]}
    for want in REQUIRED.get(cid, []):
        if not any(want in r for r in resources):
            issues.append(f"required resource '{want}' missing from {sorted(resources)}")
    # det-tasks coherence: tasks must reference their project
    if cid == "det-tasks":
        task_res = [r for r in resources if "task" in r]
        if task_res:
            eps_l = [e for e in stateful if e["resource"] == task_res[0] and e["method"] == "GET" and "{" not in e["path"]]
            body = eps_l[0]["response_body"] if eps_l else []
            fields = set().union(*[set(i.keys()) for i in body if isinstance(i, dict)]) if isinstance(body, list) and body else set()
            if not any("project" in f for f in fields) and "project" not in eps_l[0]["path"].lower() if eps_l else True:
                issues.append(f"tasks don't reference a project (fields {sorted(fields)})")

    requests.delete(f"{BASE}/api/projects/{pid}/", headers=H)
    return {"case": cid, "ok": not issues, "issues": issues, "notes": notes,
            "took": round(took, 1), "endpoints": [(e["method"], e["path"], e["mode"], e["resource"]) for e in eps]}

def main():
    H = auth()
    results = [evaluate_case(H, *c) for c in CASES]
    passed = sum(r["ok"] for r in results)
    for r in results:
        print(f"\n{'✅' if r['ok'] else '❌'} {r['case']} ({r['took']}s)")
        for m, p, mo, res in r["endpoints"]: print(f"    {m:6} {p:32} {mo:8} {res}")
        for n in r["notes"]: print(f"    · {n}")
        for i in r["issues"]: print(f"    ✗ {i}")
    print(f"\n=== {passed}/{len(results)} cases passed ===")
    json.dump(results, open(sys.argv[1] if len(sys.argv) > 1 else "eval_results.json", "w"), indent=1)

main()
