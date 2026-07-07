# ◆ Mockbird

Self-serve API mocking: define fake endpoints in a web dashboard and
instantly get a live, shareable URL that returns configurable JSON —
with adjustable latency and error simulation.

**Stack:** Vue 3 (Composition API) + Pinia + Vite · Django + DRF +
SimpleJWT · PostgreSQL (SQLite in dev).

## Quick start (local)

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # or bin/pip on unix
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py runserver 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

Register an account, create a project, add an endpoint — then call:

```
GET http://localhost:8000/m/<project-slug>/<your-path>
```

## Tests

```bash
cd backend && .venv/Scripts/python manage.py test   # 22 tests
cd frontend && npm test                             # 8 tests
```

## Configuration (env vars)

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | dev key | Django secret (set in prod!) |
| `DEBUG` | `true` | Set `false` in prod |
| `DATABASE_URL` | SQLite | e.g. `postgres://...` on Render |
| `ALLOWED_HOSTS` | `*` | Comma-separated hosts |
| `CORS_ORIGINS` | — | Comma-separated frontend origins |
| `VITE_API_BASE` | `http://localhost:8000` | Backend URL for the SPA |
| `OPENAI_API_KEY` | — | Enables ✨ AI endpoint generation |
| `AI_THROTTLE_RATE` | `10/hour` | Per-user AI rate limit |

## AI generation (optional)

Copy `backend/.env.example` to `backend/.env` and set your
`OPENAI_API_KEY`. The "✨ Generate with AI" button on a project then
turns a plain-English description into ready-made mock endpoints
(gpt-4o-mini, JSON mode, per-user rate limit). Without a key the
feature returns 503 and everything else works normally.

## Deploy

- **Frontend → Vercel:** import repo, root dir `frontend`, set
  `VITE_API_BASE` to your Render URL.
- **Backend → Render:** web service, root dir `backend`, build
  `pip install -r requirements.txt && python manage.py migrate`,
  start `gunicorn config.wsgi`, attach managed Postgres
  (`DATABASE_URL` is injected automatically).

## Dynamic mocks

- Paths support `{param}` segments (`/products/{id}`); static bodies
  can reference captures via `"{{params.id}}"`.
- **Stateful mode:** point endpoints at a named resource and CRUD
  actually works — POST inserts, PATCH merges, DELETE removes, GET
  reads live state. Seeded from the list endpoint's body; inspect
  and reset it in the dashboard's State tab.

## How the mock server works

```
Client → /m/<slug>/<path> → Django catch-all view
       → match (project, method, path) in DB
       → apply delay_ms + error_rate
       → return stored JSON + headers, log the request
```

See [COURSE.md](COURSE.md) for a chapter-by-chapter walkthrough of the
entire codebase.

MIT licensed.
