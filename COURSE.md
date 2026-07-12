# The Mockbird Course

*How to build (and fully understand) a self-serve API mocking tool
with Vue 3 + Django, chapter by chapter.*

This course retraces exactly how this repository was built, in the
order it was built, including the reasoning and the tests that drove
each step. If you follow it top to bottom you can recreate the whole
project from an empty folder.

---

## Chapter 1 — What are we building, really?

**Feynman moment (explain it like I'm five):** imagine your friend
promised to build you a lemonade stand, but it's not ready. You still
want to practice selling. So you build a *cardboard* lemonade stand
that looks and behaves like the real one — it even makes you wait in
line (latency) and sometimes says "sold out!" (errors). Mockbird is
that cardboard stand for APIs: the real backend isn't ready, so you
describe what it *would* answer, and Mockbird pretends to be it at a
real URL.

Concretely, the product loop is:

1. Sign in to a dashboard.
2. Create a **Project** → you get a stable base URL like
   `https://host/m/demo-shop-02c462`.
3. Add **Endpoints**: "when someone does `GET /users/42`, answer
   `{"id": 42, "name": "Ada"}` with status 200 after 200 ms".
4. Point your frontend (or curl, or a test suite) at that URL.
5. Watch every incoming request in a **Request log**.

Two deployable pieces:

- **Frontend:** Vue 3 SPA (Vite, Pinia, Vue Router) — just static
  files; it talks to the backend over HTTPS with a JWT.
- **Backend:** Django + DRF — serves *two different audiences*: the
  dashboard (config REST API under `/api/…`) and the whole world
  (live mocks under `/m/<slug>/…`).

That dual role of Django is the most interesting architectural idea
in the project. Keep it in mind; Chapter 5 is devoted to it.

---

## Chapter 2 — Backend skeleton and settings

Commands that created the skeleton:

```bash
mkdir backend && cd backend
python -m venv .venv
pip install django djangorestframework djangorestframework-simplejwt \
            django-cors-headers dj-database-url
django-admin startproject config .
python manage.py startapp mocks
```

Everything lives in **one app, `mocks`** — the domain is small enough
that splitting auth/projects/logs into separate apps would be
ceremony, not modularity. Modularity instead happens at the *file*
level (`models.py`, `serializers.py`, `views.py`, `mock_server.py`).

Key decisions in `backend/config/settings.py`:

- **Env-driven config.** `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`,
  `DATABASE_URL`, `CORS_ORIGINS` all read from the environment with
  safe dev defaults. This is what makes the same code run on your
  laptop (SQLite) and on Render (Postgres) with zero code changes —
  `dj_database_url.config()` parses whatever `DATABASE_URL` says.
- **DRF defaults:** every API view requires a JWT
  (`IsAuthenticated` + `JWTAuthentication`) unless it explicitly
  opts out. Secure by default; the register view opts out.
- **JWT lifetimes:** 8-hour access token (a workday), 7-day refresh.
- **CORS:** wide open in dev (`CORS_ALLOW_ALL_ORIGINS = DEBUG`),
  explicit origin list in prod.

**Why JWT and not Django sessions?** The SPA lives on a different
domain (Vercel) than the API (Render). Cookies across domains are
painful (SameSite, CSRF); a stateless `Authorization: Bearer …`
header is not. That's the whole argument.

---

## Chapter 3 — The data model (TDD begins)

Three tables carry the entire product. Before writing them, we wrote
`mocks/tests/test_models.py` — the tests *are* the specification:

- A project's slug is auto-generated and unique, even for two
  projects with the same name.
- An endpoint defaults to `200 / {} / 0ms delay / 0% errors`.
- Paths are normalized to always start with `/`.
- The same `(project, method, path)` can exist only once.

Then `mocks/models.py` makes them pass:

**`Project`** — `owner`, `name`, and a `slug` like
`demo-shop-02c462`. The slug is the public identity of the mock URL.
It's built as `slugify(name)[:32] + "-" + secrets.token_hex(3)`:
human-readable *and* unguessable enough that you can't trivially
enumerate other people's projects. Generated in `save()` so callers
never think about it.

**`Endpoint`** — the heart of the product. One row = one rule:

| field | meaning |
| --- | --- |
| `method`, `path` | the route to match |
| `status_code`, `response_body`, `headers` | what to answer |
| `delay_ms` | fixed latency simulation |
| `error_rate`, `error_status` | "fail X% of the time with status Y" |

`response_body` and `headers` are `JSONField`s — the database stores
arbitrary JSON, so users aren't restricted to any schema. A
`UniqueConstraint` on `(project, method, path)` guarantees a request
can never match two rules ambiguously.

**`RequestLog`** — an append-only record: method, path, body
(truncated), resulting status, `matched` flag, timestamp. Note
`matched=False` rows are logged too — seeing the requests that *didn't*
hit a rule is exactly how you debug a typo'd path.

**Feynman check:** if you can answer "why is the slug random-suffixed?"
and "why is there a unique constraint on three columns?", you
understand this chapter. (Answers: privacy/collisions; ambiguity.)

---

## Chapter 4 — The config REST API

Again tests first (`mocks/tests/test_api.py`): registration works,
duplicate usernames 400, unauthenticated requests 401, users see
*only their own* projects, endpoint CRUD round-trips, `error_rate`
over 100 is rejected.

The implementation (`serializers.py`, `views.py`, `config/urls.py`)
is deliberately boring DRF — boring is good:

- **`RegisterSerializer`** wraps `User.objects.create_user` (which
  hashes the password — never store it raw).
- **`ProjectViewSet`** is the classic ownership pattern, and it's
  worth internalizing:

  ```python
  def get_queryset(self):
      return Project.objects.filter(owner=self.request.user)

  def perform_create(self, serializer):
      serializer.save(owner=self.request.user)
  ```

  Filtering in `get_queryset` means another user's project id
  returns **404, not 403** — you can't even learn that it exists.
  This one idiom is the entire authorization model of the app.

- **`OwnedProjectMixin`** extends that idea to nested resources.
  Endpoints live at `/api/projects/<project_pk>/endpoints/`; the
  mixin resolves `project_pk` *through an owner-filtered queryset*,
  so every nested view inherits the same tenant isolation for free.
  That's the DRY/SOLID move: one security decision, written once.

- **URLs:** SimpleJWT gives us `/api/auth/token/` (login) and
  `/api/auth/token/refresh/` for free. A DRF router generates the
  project routes; the nested endpoint routes are wired explicitly —
  clearer than pulling in a nested-router dependency for two URLs.

---

## Chapter 5 — The mock server (the interesting part)

Everything so far is standard CRUD. This chapter is the product.

**Feynman moment:** a normal web framework is a receptionist with a
printed directory: "requests for `/users` go to office A" — the
directory is written by programmers and fixed at deploy time.
Mockbird's mock server is a receptionist whose directory is a
*whiteboard that visitors themselves write on*. When a request
arrives, she reads the whiteboard (the database) fresh, every time.
Routes are **data, not code** — that inversion is the whole trick.

`mocks/mock_server.py`, driven by nine tests in
`test_mock_server.py`:

```
/m/<slug>/<any/path>  →  MockServerView.dispatch()
    1. find Project by slug        → 404 JSON if unknown
    2. find Endpoint by (project, request.method, "/" + path)
       → 404 JSON + log(matched=False) if none
    3. sleep(delay_ms / 1000)               # latency simulation
    4. roll d100 ≤ error_rate ? error_status : status_code
    5. JsonResponse(response_body) + custom headers
    6. log the request
```

Implementation notes worth understanding:

- **We override `dispatch`, not `get`/`post`.** Django's `View`
  normally fans out by HTTP method — but our method dispatch happens
  in the *database query* (`method=request.method`), so one code
  path handles every verb.
- **`@csrf_exempt`** — mock consumers are external clients, not
  browser forms; they have no CSRF token and never will.
- **Delay is capped at 30 s** (`MAX_DELAY_MS`) so a user can't
  configure a 10-minute sleep and pin down server workers.
- **Error simulation** is one line: `random.randint(1, 100) <=
  error_rate`. The test pins `error_rate=100` to make the randomness
  deterministic; the delay test patches `time.sleep` instead of
  actually sleeping — two standard tricks for testing
  time/randomness.
- **Logging truncates the body at 10 kB** and decodes with
  `errors="replace"` — someone POSTing 50 MB of binary junk must not
  crash the logger or bloat the table.

Everything else in the repo exists to write rows that this ~70-line
file reads.

---

## Chapter 6 — Frontend architecture

```bash
npm create vite@latest frontend -- --template vue
npm i pinia vue-router axios
npm i -D vitest @vue/test-utils jsdom
```

Layered like the backend, one concern per file:

```
src/
├── api/client.js        # axios + JWT plumbing (the ONLY http config)
├── stores/              # Pinia: auth, projects, endpoints (+ logs)
├── router/index.js      # routes + auth guard
├── views/               # one component per page
├── components/          # reusable pieces
└── styles/main.css      # design system
```

**`api/client.js`** is the most load-bearing file. Two interceptors:

1. *Request:* attach `Authorization: Bearer <access>` from
   localStorage — so no store or component ever thinks about auth
   headers.
2. *Response:* on a 401, try `POST /api/auth/token/refresh/` once
   (an `_retried` flag prevents infinite loops), store the new
   access token, and transparently replay the original request. To
   the rest of the app, expired tokens simply never happen.

**Pinia stores** hold server state and are the only place `client`
is called. Components never import axios. Each action follows the
same shape: call API → mutate local state to match
(`unshift`/`filter`/`findIndex`), so the UI updates instantly without
a refetch. `auth` hydrates from localStorage at startup, which is why
a page reload keeps you signed in.

**Router guard** (`router/index.js`) — routes are private by
default; `meta: { public: true }` marks the two auth pages.
Unauthenticated → redirected to login; authenticated visiting login →
bounced to the dashboard. Same "secure by default" philosophy as the
DRF permission setting — notice the symmetry.

**Views vs components:** views (`Login`, `Register`, `Dashboard`,
`ProjectDetail`) own data-fetching and route params; components
(`NavBar`, `AuthCard`, `ProjectCard`, `EndpointRow`, `EndpointForm`,
`LogsTable`, `CopyButton`) are dumb: props in, events out
(`@edit`, `@delete`, `@save`). That props-down/events-up discipline
is what makes `EndpointRow` trivially unit-testable.

`EndpointForm` deserves a note: `response_body` is edited as *text*
in a monospace textarea and validated with `JSON.parse` before
emitting — parse errors surface inline instead of as a server 400.

---

## Chapter 7 — The design system

One file, `styles/main.css`, no framework. For an app this size a
utility framework (Tailwind) or component library would add build
complexity without paying rent; custom properties + a handful of
classes are enough.

The corporate-modern recipe used here:

- **Tokens first:** `--brand` (indigo `#4f46e5`), slate text tones,
  one radius, two shadows — every component consumes the same
  variables, which is *why* the app looks coherent.
- **Typography:** Inter for UI, JetBrains Mono for anything that is
  code (paths, URLs, JSON) — the mono font instantly signals "this
  is machine-facing".
- **Depth:** cards with hairline borders + soft shadows; primary
  buttons carry a subtle gradient and a colored glow shadow.
- **Motion:** a single easing curve
  (`cubic-bezier(0.22, 1, 0.36, 1)` — fast start, gentle landing)
  used everywhere. Vue transitions: `fade` between routes, `rise`
  (fade + translate up) on page mounts and modals,
  `<transition-group name="list">` so created/deleted
  endpoints/projects animate in and out instead of popping.
  Buttons compress on `:active` (`scale(0.97)`) for tactility.
- **Glassmorphism accent:** sticky navbar with
  `backdrop-filter: blur`; auth pages sit on soft radial gradients.

**Feynman moment:** why do design tokens make everything look
"professional"? Because human eyes are excellent inconsistency
detectors. Five slightly different blues read as sloppy even if no
single one is ugly; one blue used five times reads as intentional.
Tokens make consistency the default rather than a discipline.

---

## Chapter 8 — Testing strategy across the stack

The pyramid, as actually applied here:

| Layer | Tool | What we assert |
| --- | --- | --- |
| Models (6 tests) | Django `TestCase` | slug rules, defaults, constraints |
| Config API (7) | DRF `APITestCase` | auth, ownership isolation, CRUD, validation |
| Mock server (9) | Django test client | matching, 404s, delay, error %, logging |
| Stores (6) | Vitest + mocked `client` | state transitions per action |
| Components (2) | Vitest + Vue Test Utils | rendered output, emitted events |

Principles worth stealing:

- **Test behavior through public interfaces.** Every backend test
  speaks HTTP (or the model API); no test reaches into internals.
  Frontend store tests mock only the boundary (`api/client`).
- **Make nondeterminism deterministic at the edges:** patch
  `time.sleep`, pin `error_rate=100`.
- **Ownership tests are security tests.** `test_cannot_access_others_project`
  is the most important test in the repo.

One real-world war story from this build: on Node ≥ 22, Node ships an
*experimental* `localStorage` global that is `undefined`-ish and
shadows jsdom's working one, so store tests crashed on
`localStorage.clear()`. Fix: `vitest.setup.js` installs a tiny
in-memory shim when the global is unusable. Lesson: test-environment
bugs are real bugs; fix them in setup files, not by contorting tests.

---

## Chapter 9 — Running, deploying, extending

**Local:** two terminals — `manage.py runserver 8000` and
`npm run dev`; the SPA defaults to `http://localhost:8000` via
`VITE_API_BASE`.

**Production topology:**

```
Browser ── static SPA ──► Vercel (CDN)
   │ JWT / JSON
   ▼
Render: gunicorn + Django ──► managed Postgres
   ▲
   └── any HTTP client hitting /m/<slug>/…
```

Render injects `DATABASE_URL`; you set `SECRET_KEY`, `DEBUG=false`,
`ALLOWED_HOSTS`, `CORS_ORIGINS`. Vercel just needs `VITE_API_BASE`.
Nothing in the code changes between environments — that was the point
of Chapter 2.

**Extension ideas, in the order the architecture invites them:**

1. **Path parameters** (`/users/{id}`) — replace the exact-match
   query in `mock_server.py` with pattern matching; everything else
   stays.
2. **Response templating** (echo request data into the body).
3. **Live log streaming** — WebSocket/SSE instead of the refresh
   button.
4. **Team sharing** — a `Membership` model; the ownership queryset
   from Chapter 4 is the single place to widen.

---

## Chapter 10 — A touch of AI: describe an API, get its mock

> **Historical note:** this chapter describes the AI feature as it
> was *first* built — a synchronous call to OpenAI's `gpt-4o-mini`.
> The current code no longer works this way: Chapter 14 rebuilds it
> around a local model (qwen3:1.7b via Ollama) and Chapter 15 makes
> it asynchronous. Read this chapter for the design principles
> (untrusted output, validation, throttling), which all survived the
> rewrite.

On a project page, "✨ Generate with AI" takes a plain-English
description ("a todo API with list, detail, create, delete…") and
creates real endpoints. Three files carry it.

**`mocks/ai.py` — the boundary with the model.** We call OpenAI's
`gpt-4o-mini` (cheap, fast) over plain HTTP with
`response_format: {"type": "json_object"}` — JSON mode — and a system
prompt that pins the exact output shape, limits methods, and demands
concrete paths (no `{id}` placeholders, because our matcher is
exact-match; see Chapter 5).

The crucial discipline: **never trust model output.**
`parse_endpoints()` treats the LLM like any untrusted client — it
drops unknown methods, normalizes paths, clamps `status_code` to
100–599 and `delay_ms` to the same 30 s cap the mock server enforces,
and caps the list at 10. Any failure (network, bad JSON, missing key)
collapses into one domain exception, `AiUnavailable`, which the view
maps to a 503. The rest of the codebase never learns OpenAI exists.

**`AiGenerateView`** reuses `OwnedProjectMixin` (tenant isolation for
free, again), skips definitions that would collide with existing
`(method, path)` routes, bulk-creates the rest, and returns them
through the same `EndpointSerializer` as manual creation.

**Rate limiting** is DRF's `ScopedRateThrottle` with scope `"ai"` —
one settings line (`AI_THROTTLE_RATE`, default `10/hour` per user)
and one attribute on the view. Only this endpoint is throttled;
normal CRUD stays unlimited. Over the limit → 429, which the modal
translates to "Rate limit reached".

**Feynman moment:** the AI here is a *form-filler, not an oracle*.
Nothing it produces is executed or trusted — it just pre-populates
the same rows a human would have typed into the endpoint form, and
every value passes through the same validation. That's the safe
pattern for sprinkling LLMs into a CRUD app: let the model draft,
let your existing pipeline decide.

**Iteration after real use (v2 of the feature).** First user
feedback: generated endpoints felt unrelated ("just static rows"),
and nothing told the caller what query params or body to send. Three
fixes, worth studying because they show how feedback maps to layers:

1. *Coherence* was a **prompt** problem: the system prompt now forces
   the model to invent one small dataset first and derive every
   endpoint from it — so the list's ids match the detail routes and
   an order's total actually equals price × quantity.
2. *Missing input docs* was a **schema** problem: `Endpoint` gained
   `description` and `request_example` (JSONField documenting
   expected `query_params`/`body`), filled by the AI, editable by
   hand, shown when you expand an endpoint row.
3. *"How do I try it?"* was a **UX** problem: a ▶ Test button opens
   `MockTester.vue`, which fires a real `fetch` at the live mock URL
   (pre-filled from `request_example`), and shows status, latency,
   and pretty-printed body — and, since it's a genuine request, it
   also lands in the request log.

Testing note: all tests in `test_ai.py` patch
`generate_endpoints` (or feed `parse_endpoints` directly) — the suite
never touches the network and runs without an API key.

---

## Chapter 11 — Dynamic mocks: path params and stateful CRUD

The extension Chapter 5 predicted. Two upgrades turn Mockbird from a
tape recorder into something that behaves like a real API.

**Path parameters (`mocks/matching.py`).** Paths may now contain
`{param}` segments (`/products/{id}`). `find_endpoint()` tries an
exact match first (cheap, and specific routes like
`/products/special` must beat patterns), then compares
segment-by-segment against pattern routes, capturing params. Static
endpoints can splice captures into their body with
`"{{params.id}}"` — `render_template()` walks the JSON recursively
and substitutes.

**Stateful CRUD (`mocks/stateful.py` + the `Resource` model).**

*Feynman moment:* the old mock server was a tape recorder — ask,
and it plays the same tape. A stateful mock is a whiteboard with an
actual list on it: POST writes a new line, DELETE erases one, and
the next GET reads whatever the whiteboard says *now*.

The whiteboard is `Resource`: a named JSON collection per project
with two copies of the data — `initial_items` (the seed, written
once) and `items` (live state, mutated by traffic). An endpoint
with `mode="stateful"` and `resource="products"` no longer returns
its stored body; instead `handle_stateful()` derives the operation
from shape alone:

| request | operation |
| --- | --- |
| GET, no param | return all `items` |
| GET `/…/{id}` | return matching item or 404 |
| POST | insert body with next integer id → 201 |
| PUT / PATCH `/…/{id}` | replace / merge → 200 (404 if missing) |
| DELETE `/…/{id}` | remove → 204 (404 if missing) |

No per-operation configuration — five endpoint rows sharing one
resource name give you a working, persistent, shareable fake API.
Delay and error simulation still apply on top (the dispatch order
in `mock_server.py`: match → delay → error roll → stateful/static).

Seeding is one shared function, `seed_resource()` in `views.py`:
when a stateful endpoint is created (by hand or by AI) and its
`response_body` is a list, that list becomes the resource's seed —
the AI's coherent dataset from Chapter 10 flows straight into live
state. The **State tab** in the dashboard shows each resource's
current items and a "Reset state" button (`POST
/resources/<id>/reset/` copies `initial_items` back over `items`) —
essential once tests start mutating things.

Design choice worth noting: state lives in a JSONField, not in
dynamically created tables. Mock data is small, schema-free, and
disposable; a real table per user-defined resource would be
enormous complexity for zero benefit here. Knowing when *not* to
normalize is also data modeling.

---

## Chapter 12 — Growing the product: import, live logs, public docs

Three features added in one sweep, each reusing machinery from
earlier chapters — a sign the architecture is paying rent.

**OpenAPI import (`mocks/openapi_import.py`).** Teams that would
adopt Mockbird usually already *have* an API spec. `parse_openapi()`
walks a pasted/uploaded Swagger 3.x document (YAML or JSON — YAML is
a superset, so one `yaml.safe_load` handles both) and emits the same
definition dicts the AI produces, so `create_endpoints()` — the
shared bulk-create-with-dedup helper extracted from the AI view —
serves both. Happy accident worth noticing: OpenAPI's path
templating (`/pets/{petId}`) is *identical* to our Chapter 11
`{param}` syntax, so paths pass through untouched. Response bodies
prefer explicit `example`s; otherwise `_example_from_schema()`
synthesizes one from the JSON schema (object → recurse properties,
array → one item, scalars → type defaults, depth-capped).

**Live request log via SSE (`mocks/streaming.py`).** Server-Sent
Events is the right tool when data flows one way (server → browser):
it's plain HTTP, auto-reconnects, and needs no websocket
infrastructure. Two implementation realities dominate the file:

1. `EventSource` cannot set an `Authorization` header, so the JWT
   rides in `?token=` and is validated manually with
   `JWTAuthentication` — same tokens, different transport.
2. A streaming response holds a server worker for its lifetime, so
   the generator polls the DB every 2 s and hard-stops after 5
   minutes (the browser transparently reconnects). Testable because
   the generator `iter_log_events()` is a plain function — the test
   patches `time.sleep` and pulls two frames off it.

The frontend opens the stream when the log tab is active (pulsing
"live" dot), prepends events through the existing
`<transition-group>`, and closes it on tab switch or unmount.

**Public docs (`PublicDocsView` + `DocsView.vue`).** One
`AllowAny` endpoint keyed by the unguessable slug returns name +
endpoint definitions — nothing else (the test asserts no owner/log
leakage; capability-URL security, same idea as the mock URL itself).
The SPA renders it at `/docs/<slug>` as a clean API-reference page:
method badges, descriptions, request examples, response/seed JSON.
A router nuance: the guard bounced *authenticated* users off public
routes (fine for login/register, wrong for docs), fixed with a
`standalone` meta flag — guards accrete special cases; keep them
declarative.

---

**Checkpoint — Feynman test:** close this file and explain, out loud,
what happens end-to-end when `GET /m/demo-shop-x1/users/42` arrives —
from TCP hitting gunicorn to JSON leaving and a log row appearing. If
you can narrate every hop (URLconf → `MockServerView.dispatch` → two
DB lookups → sleep → dice roll → `JsonResponse` → `RequestLog`), you
understand everything up to this point. The remaining chapters cover
how the project left the laptop: real deployment, and rebuilding the
AI feature around a *small local model* instead of a paid API.

---

## Chapter 13 — Deployment: two containers and a traffic cop

**Feynman moment:** in development you run two programs on two ports
(Vite on 5173, Django on 8000) and the browser is told "the API lives
somewhere else" — which is why CORS exists at all. In production we
do something simpler and older: put *one* front door (nginx) in front
of everything, so the browser only ever talks to one origin. No CORS,
no `VITE_API_BASE`, no mixed-content headaches. nginx is the traffic
cop standing at that door deciding, per URL, which room you go to.

Three files (`Dockerfile.web`, `backend/Dockerfile`, `nginx.conf`)
define the whole stack:

**The web image** is a two-stage build: stage 1 (node) runs
`npm run build` with `VITE_API_BASE=` **empty** — so the SPA makes
same-origin requests like `/api/projects/` — and stage 2 (nginx)
keeps only the built `dist/` plus the config. The node toolchain
never ships to production; the final image is nginx + static files.

**The routing rules in `nginx.conf`** mirror the app's URL design
from Chapter 2 (this is where the `/api/`, `/m/`, `/admin/` prefixes
pay off — one prefix per `location` block):

- `/api/` → Django, with `proxy_buffering off` and a 600 s read
  timeout. Both matter for streaming: buffering would hold SSE
  frames hostage until the buffer fills, and the default 60 s
  timeout would kill long log streams and slow AI generations.
- `/m/` → Django. This is the URL users share with third parties.
- everything else → `try_files $uri $uri/ /index.html` — the classic
  SPA fallback: unknown paths return `index.html` so Vue Router can
  handle `/projects/7` client-side after a hard refresh.

One non-obvious line: `resolver 127.0.0.11` + a variable upstream
(`set $mockbird_upstream …; proxy_pass $mockbird_upstream`). With a
literal hostname nginx resolves it *once at startup* and dies if the
API container isn't up yet; a variable forces per-request DNS
resolution via Docker's internal resolver, so start order stops
mattering.

**The API image** runs migrations then gunicorn with
`--worker-class gthread --workers 2 --threads 8`. Why threads and not
just processes? Mockbird's workload is dominated by *waiting*:
`time.sleep` for simulated latency, 2 s polls in SSE streams, minutes
inside AI generation. Threads are cheap for waiting; 2×8 gives 16
concurrent requests without 16 processes' worth of RAM. The
`--timeout 300` matches the AI path's worst case — a worker mid-
generation must not be shot by gunicorn's watchdog.

**Feynman test:** why can the deployed frontend call `/api/…` with no
CORS configuration at all, while dev needs `corsheaders`? (Answer:
same origin — CORS is a *browser* rule about origins, and nginx makes
the origins identical. Dev has two ports, hence two origins.)

---

## Chapter 14 — AI v3: swapping the oracle for a local model

Chapter 10's design ("the model is an untrusted form-filler") gets
stress-tested: replace `gpt-4o-mini` with **qwen3:1.7b on a local
Ollama** — a model thousands of times smaller. Everything in this
chapter follows from one fact: *small models are bad at big asks*.

**The provider becomes a config knob.** Ollama speaks the
OpenAI-compatible `/chat/completions` protocol, so `_call_model()`
needs no provider branches — just `AI_BASE_URL` / `AI_MODEL` /
`AI_API_KEY` settings (defaults: `localhost:11434/v1`, `qwen3:1.7b`).
Point the base URL at `api.openai.com/v1` and it's OpenAI again.
Lesson: when an ecosystem converges on a wire protocol, depend on the
protocol, not the vendor.

**One big prompt becomes two small ones.** Asking a 1.7B model for
"complete coherent endpoint definitions" produced garbage. The fix in
`ai.py` is a pipeline where the model only does what models are good
at and *code does the rest*:

1. **Plan** (`_plan_resources`): "extract 1–5 resources with example
   fields and sensible actions" — a short, factual task. Output is
   distrusted as ever: names slugified, placeholder echoes like
   `plural_resource_name` dropped via `FORBIDDEN_NAMES`, up to 4
   retries with slightly rising temperature (0.0 + 0.3·attempt —
   deterministic first try, diversity only on retry).
2. **Records** (`_gen_records`): per resource, "write 3–4 realistic
   records with exactly these fields" — the creative part, run in a
   `ThreadPoolExecutor` since calls are independent. If both attempts
   fail, the plan's example record seeds state anyway: degraded, not
   broken.
3. **Assemble** (`_crud_endpoints`): the CRUD family — list GET,
   detail GET, POST/PATCH/DELETE per the plan's `actions` — is built
   *deterministically in code*. The model never writes a path or a
   status code again.

**Feynman moment:** v2 asked the intern to design the filing cabinet
*and* fill it. v3 asks the intern only to name the folders and invent
the paperwork — the cabinet is built by machine, identical every
time. The smaller your intern, the more of the job you move into the
machine.

Around the pipeline sit deterministic repair passes, each one a
patched-over observed failure of the small model: `_link_parents()`
regex-detects "projects contain tasks" and injects the `project_id`
the model forgot; `_ensure_ids()` fixes duplicate/missing ids that
would break id-based CRUD; `_extract_json()` strips `<think>` blocks
and code fences (qwen3 is a reasoning model — and the `/no_think`
suffix in the user message stops it from spending its whole token
budget thinking and returning empty content); `normalize_endpoints()`
rewrites literal `/books/3` to `/books/{id}`, dedupes routes, forces
whole families stateful, and synthesizes a missing list GET so state
always seeds.

**How do you know any of this works? You measure it.**
`tools/ai_eval.py` is an eval harness — the LLM-era equivalent of a
test suite, run against a live server because model output is
nondeterministic. Ten cases from vague ("a todo app", "something for
my gym") to detailed specs, each checked on three levels: structural
(≥3 endpoints, no duplicate routes, stateful families exist),
semantic (domain keywords appear in resources/paths — a gym API must
mention members or workouts), and **behavioral**: it calls the live
`/m/` mock — list must return seeded items, POST must appear in the
next list, DELETE must remove. The prompts and repair passes above
weren't designed up front; they were iterated until the eval passed.
That workflow — change prompt, run eval, read failures — is the
central skill of building on small models.

---

## Chapter 15 — Going async: the job that outlives the request

A local model can take minutes. Chapter 10's synchronous
request→response AI call breaks twice: proxies (Cloudflare, nginx
defaults) cut connections around 100 s, and a browser spinner with no
feedback for two minutes feels dead. The rebuilt flow in `views.py`
is a homemade background-job system — worth studying because it shows
what Celery/RQ would give you, built from parts you already have.

**The shape:** `POST /generate/` validates, writes
`{"percent": 1, "status": "running"}` into a new
`Project.ai_progress` JSONField, spawns a **daemon thread**, and
returns `202 Accepted` immediately. The client then polls
`GET /generate/progress/` once a second; the same field later carries
`"done"` or `"error"`, so the poll is also the delivery channel for
the outcome. The gthread worker config from Chapter 13 is what makes
"just a thread" viable.

**Feynman moment:** ordering at a restaurant. Sync was standing at
the counter staring at the cook. Async is: you get a buzzer (202),
the kitchen writes its status on a board (`ai_progress`), and you
glance at the board whenever you like. The buzzer never lies, because
`_run_generation` catches *every* exception and writes an error state
— the one unforgivable bug in a polling design is a client polling
forever.

Details that make it production-grade rather than a toy:

- **Threads need DB hygiene:** `_generation_worker` wraps the run in
  `close_old_connections()` — Django manages connections per thread,
  and a thread that borrows one and exits leaks it.
- **Fair use of one GPU:** `generation_slot()` caps *server-wide*
  concurrent generations (default 3) using **Postgres advisory
  locks** — `pg_try_advisory_lock(namespace, slot)` — because a
  Python lock only covers one process and gunicorn runs several.
  The database is the only thing all workers already share, so it
  becomes the coordinator; no Redis needed. Non-blocking `try` means
  a full house returns "capacity in use, try again" instantly rather
  than queueing invisibly. Per-user fairness stays with the DRF
  throttle (`6/min`); the advisory locks protect the *hardware*.
- **Watching the model think:** every streamed token from
  `_call_model` (it requests `stream: True` and reads the SSE deltas)
  flows into `_GenerationLog`, which groups tokens into labeled
  sections per model call, keeps the last 8000 chars, and — the
  important bit — flushes to `ai_progress` at most ~2×/second, not
  per token. UPDATE-per-token would hammer the DB for a display the
  human reads at 2 Hz anyway. The modal (`AiGenerateModal.vue`)
  renders it as a terminal-style `<pre>` pinned to the newest tokens.
  Progress percent, meanwhile, comes from the *pipeline structure*:
  plan = 5→30 %, records = 30→85 % (advancing per resource), assembly
  = 90 %. Honest milestones, not a fake animated bar.
- **Testing async without flakiness:** the `AI_RUN_SYNC` setting
  makes tests run the worker inline. The seam between "how it runs"
  and "what it does" (`_generation_worker` vs `_run_generation`) is
  exactly what makes that a one-line switch.

---

**Final Feynman test:** explain the *other* end-to-end journey — a
user types "restaurant reservations app" and clicks Generate. Narrate
it: 202 + progress row → daemon thread → advisory-lock slot → plan
call to Ollama (tokens streaming into the throttled log) → parallel
record calls → deterministic CRUD assembly and repair passes →
`create_endpoints` + `seed_resource` → `"done"` picked up by the
poll → and now `GET /m/<slug>/reservations` serves seeded state
through the Chapter 5/11 machinery, via the nginx `/m/` block from
Chapter 13. If you can also say *why* each piece exists — why 202,
why advisory locks, why two prompts instead of one, why the eval
harness is the real spec — you can rebuild this project, and more
importantly you could re-derive it under different constraints.
That's expert.
