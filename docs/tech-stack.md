# FieldSync — Technology Stack & Tooling Decisions

**Doc ID:** FS-TSD-01 · **Version:** 0.1 · **Status:** draft — under review
**Companion docs:** [`architecture.md`](./architecture.md) · [`system-design.md`](./system-design.md) · [`data-model.md`](./data-model.md) · [`data-flow-diagram.md`](./data-flow-diagram.md) · `repo-structure.md`

Every tool below is chosen against the goals, SLOs, and non-goals already fixed in `system-design.md` §2–3 — this document exists so a choice can be checked against those numbers later instead of re-litigated from taste. Each major decision follows the same shape: **Context → Options considered → Decision → Consequences**. Minor, lower-stakes tool choices are grouped into one reference table in §2.

## 1. Decisions with real trade-offs

### D1 — API paradigm: REST, GraphQL, or gRPC

**Context.** Three kinds of traffic exist: role-scoped CRUD over a small, fixed set of resources (jobs, agents, notifications); a live, high-frequency stream (location pings, status changes, chat); and, in v1, exactly one client type — a browser (see `system-design.md` §1, native mobile is out of scope). The question is which paradigm fits *both* the CRUD side and the streaming side without adding a second stack.

| Criterion | **REST + WebSocket** (chosen) | GraphQL | gRPC |
|---|---|---|---|
| Fits a small, fixed resource set | Yes — 12 endpoints total, per `architecture.md` §5 | Overkill — its strength is flexible querying across a large, evolving graph FieldSync doesn't have | N/A — not a query model |
| Native browser support | `fetch` + native `WebSocket`, no extra client library | Needs a GraphQL client (Apollo/urql) even for simple calls | Needs gRPC-web + a proxy; browsers can't speak gRPC directly |
| Real-time fit | Native WebSocket via Channels — one connection, arbitrary server-push, exactly the `group_send` fan-out in `architecture.md` §3 | Subscriptions exist but are a secondary, less mature feature bolted onto a request/response model | Bidirectional streaming is a first-class feature — but built for service-to-service, not browser clients |
| Tooling / docs | `drf-spectacular` → OpenAPI 3 → Swagger UI at `/api/docs/`, already assumed in `architecture.md` §5 | Needs its own schema tooling (GraphiQL, schema-first codegen) | `.proto` + generated stubs; excellent for polyglot services, irrelevant for one Django monolith |
| Caching | Standard HTTP caching semantics (ETags, `Cache-Control`) work unmodified | Everything is a `POST` to one endpoint — HTTP caching doesn't apply by default | N/A, not cache-oriented |
| Team learning curve | Everyone already knows REST; the DRF permission/serializer pattern in `architecture.md` §5 is standard | Resolver design, N+1 query pitfalls (`select_related`/`prefetch_related` discipline becomes load-bearing) | Protobuf schema design, streaming semantics — a real learning investment for no payoff here |
| Where it *would* win | — | A client that needs to compose many nested resources in one round trip (e.g. a future analytics dashboard) | Backend-to-backend calls once FieldSync stops being one monolith (e.g. a separate billing service) |

**Decision.** REST (DRF) for every resource operation, native WebSocket (Django Channels) for everything real-time. One write path either way, per `architecture.md` §5's "REST is the only thing that writes" rule — WebSocket messages call the same service functions, they just arrive over a different transport.

**Consequences.** Every new resource is a DRF viewset, not a schema change across two systems. The cost: a client that wants three related resources makes three calls, not one — acceptable at FieldSync's fixed, small screen count (dispatcher map, agent job view, customer job view). Revisit if a client needs deeply nested, client-driven queries — see §4.

### D2 — Web framework: Django vs FastAPI vs Flask

| Criterion | **Django 5 + DRF** (chosen) | FastAPI | Flask + extensions |
|---|---|---|---|
| Batteries included | ORM, migrations, admin, auth scaffolding, permissions — all the pieces `architecture.md` §4–5 assumes exist | Fast, async-native, but ships none of the above — each is a separate library choice | Same gap as FastAPI, plus less async-native than either |
| Real-time in the same codebase | Django Channels reuses the same models, settings, and ORM — one deploy unit per `system-design.md` §4 | Would need a separate WebSocket layer (e.g. raw `starlette` websockets) with no equivalent to Channels' group/broadcast model | No first-party equivalent; would mean bolting on `Flask-SocketIO` and losing the ASGI-native story |
| Admin site | Free CRUD/audit UI for internal ops (viewing `JobEvent` history without building a screen for it) | None built-in | None built-in |
| Async story | Views can be sync or async; consumers are async by nature; `database_sync_to_async` bridges them (`architecture.md` §3) | Fully async-first, which is a better fit for a *pure* API but buys nothing extra for the WS side, which still needs Channels' group machinery | Historically sync (WSGI); async support is newer and less battle-tested |
| Maturity for this domain | `django-guardian`/custom permission classes, `simplejwt`, `drf-spectacular` are all mature and Django-specific | Would need FastAPI-native equivalents, some less mature | Same |

**Decision.** Django 5 + Django REST Framework, run as a single ASGI application (per `architecture.md` §2). FastAPI is the better tool for a pure, greenfield async API with no admin/ORM needs — FieldSync needs both a relational data model with migrations *and* a real-time layer sharing it, which is Django+Channels' specific niche.

### D3 — Real-time transport: WebSocket (Channels) vs SSE vs polling vs gRPC streaming

| Option | Fit for FieldSync |
|---|---|
| **WebSocket via Django Channels** (chosen) | Bidirectional — needed because agents *send* location pings and chat, not just receive. One connection carries all three message types (`location.ping`, `chat.message`, and server-pushed `job.update`/`notify`) per `architecture.md` §6. |
| Server-Sent Events (SSE) | One-directional (server→client) only — would still need a second channel (plain POST) for the agent's location pings and chat, doubling the transport surface for no benefit. |
| Long polling | Meets none of the `system-design.md` §3 latency targets (p95 < 500ms) without hammering the server; only ever a fallback, not a design. |
| gRPC bidirectional streaming | Solves the same problem, but for browser clients only through gRPC-web plus a proxy translating to HTTP/1.1 — an extra moving part with no payoff over native WebSocket for a browser-only v1. |

**Decision.** WebSocket via Channels, exactly as specified in `architecture.md` §6. Revisit only if a non-browser client (e.g. a native mobile agent app) needs a transport gRPC serves natively — an explicit non-goal today per `system-design.md` §1.

### D4 — AuthN/AuthZ: JWT vs server-side sessions vs OAuth2/OIDC

**Context.** `system-design.md` §4 fixes the web tier as N *stateless* ASGI replicas behind a load balancer — any replica must be able to serve any request with no sticky-session requirement. Auth has to hold up under that constraint for both REST and WebSocket connections.

| Criterion | **JWT** (chosen) | Server-side sessions | OAuth2 / OIDC (external IdP) |
|---|---|---|---|
| Fits stateless replicas | Yes — any replica verifies a token with no shared-state lookup beyond the revocation check | Needs a shared session store (DB- or Redis-backed) hit on *every* request — extra latency on the p95 budget in `system-design.md` §3 | Same statelessness benefits as JWT once tokens are issued, but adds a federation layer |
| Works identically for REST and WS | One token, sent as a header on REST and via query string/subprotocol on WS connect — one auth code path, per `architecture.md` §6 | Cookie-based sessions complicate a non-browser field-agent client and raise CSRF questions on state-changing WS messages | Same token mechanics as JWT once issued — the added complexity is entirely in the *issuing* flow |
| Revocation | Short 15-minute access token + rotated refresh, backed by `OutstandingToken`/`BlacklistedToken` (`data-model.md`) — narrows, doesn't eliminate, the window (risk R-2 in `system-design.md` §9) | Instant — deleting the session row revokes immediately | Same instant revocation is possible, but only by delegating trust to a third party |
| Fits the actual requirement | Three roles, one identity provider (FieldSync itself), no enterprise federation needed in v1 | Sufficient, but couples every request to a store lookup for no isolation benefit gained | Solves a problem FieldSync doesn't have yet — enterprise SSO is an explicit non-goal (`system-design.md` §1) |

**Decision.** JWT via `djangorestframework-simplejwt`: 15-minute access token, rotated refresh token, blacklist app enabled. Exactly the mechanism `system-design.md` §6 (L2 · AuthN) already specifies — this section is the *why*, that section is the *what*.

**Consequences.** No built-in "log out everywhere" without the blacklist table being checked on every request — a small latency cost accepted for now. Revisit toward OAuth2/OIDC only if/when an enterprise customer requires SSO.

## 2. Supporting stack

Lower-stakes in the sense that switching later is a swap, not a redesign — but each one is still a deliberate choice, not a default.

| Concern | Chosen | Why | Considered and rejected |
|---|---|---|---|
| Database | **PostgreSQL 16** | Native `UUID`, array (`AgentProfile.skills`), and strong relational integrity fit the audit-trail/state-machine model in `data-model.md` exactly | MySQL — weaker array/JSON ergonomics; MongoDB — would fight, not support, the strict FK/state-machine model this schema depends on |
| Channel layer + broker | **Redis 7** (dual role) | Channels' `channels_redis` and Celery both speak Redis natively; one moving part instead of two, an explicitly accepted trade-off (risk R-1, `system-design.md` §9) | RabbitMQ — better broker semantics alone, but not a supported Channels layer backend, which would mean running *two* systems instead of one |
| Background jobs | **Celery 5 + beat** | Mature retry/backoff/idempotency primitives (`architecture.md` §7), the widest Django integration and documentation | RQ — simpler but weaker scheduling; Dramatiq — smaller ecosystem; Django-Q — less active maintenance |
| API schema/docs | **drf-spectacular** | OpenAPI 3.1, native DRF introspection, generates the `/api/docs/` Swagger UI referenced throughout `architecture.md` | drf-yasg — OpenAPI 2 only, maintenance has slowed |
| Containerization | **Docker + Compose (v1)**, multi-stage Dockerfile | Matches the service topology in `system-design.md` §4/§7 exactly at 2–3 replicas; no orchestration complexity this scale doesn't need | Kubernetes — the correct *next* step once replica count needs autoscaling/self-healing beyond what Compose offers, not a v1 requirement |
| CI/CD | **GitHub Actions** | Zero extra infra, native Docker build/publish actions, matches `.github/workflows/ci.yml` in `architecture.md` §8 | GitLab CI / CircleCI — equally valid, just not where the repo lives |
| Testing | **pytest + pytest-django + pytest-asyncio + factory_boy + coverage.py** | `pytest-asyncio` and Channels' `WebsocketCommunicator` are the only realistic way to test the consumers in `architecture.md` §6; `factory_boy` keeps fixtures maintainable as `data-model.md`'s schema grows | Django's built-in `unittest.TestCase` — works, but fixtures/parametrize in pytest cut real boilerplate |
| Code quality | **ruff** (lint + format) + **mypy** (+ `django-stubs`, `djangorestframework-stubs`) | One fast tool instead of three; full type checking is an explicit target in `architecture.md` §9 | Separate `flake8` + `black` + `isort` — functionally equivalent, strictly more config to maintain |
| Observability | **Sentry** (errors) + **structlog** (structured JSON logs) + **django-prometheus** (metrics) | Directly produces the log fields and alert signals `system-design.md` §8 already specifies | Rolling a custom logging/metrics pipeline — not worth building versus adopting at this scale |
| Frontend | **Vanilla HTML + JS + Leaflet.js** | Three small, mostly-read-only, role-specific pages — no state-management problem a framework would earn its keep solving, per `architecture.md`'s explicit "thin frontend" decision | React/Vue SPA — a build toolchain and client-state layer disproportionate to three simple views |

## 3. Decision log

| ID | Decision | Status |
|---|---|---|
| D1 | REST (DRF) for resources, WebSocket (Channels) for real-time — no GraphQL, no gRPC | accepted |
| D2 | Django 5 + DRF, single ASGI app | accepted |
| D3 | WebSocket via Channels, not SSE/polling/gRPC streaming | accepted |
| D4 | JWT (simplejwt), not sessions or external OAuth2/OIDC | accepted |
| D5–D14 | Supporting stack, §2 | accepted |

## 4. What would make us revisit this

Each row below is a concrete trigger, not a vague "at scale" — matched to thresholds already fixed in `system-design.md` §3 and §7.

| If this happens | Revisit |
|---|---|
| A native mobile agent app is built and needs offline-friendly, client-driven field selection across nested resources | GraphQL, for that client only — REST for the browser dispatcher/customer views can stay as-is |
| FieldSync splits into more than one backend service (e.g. a separate billing service) that need to call each other | gRPC, for service-to-service calls only — never client-facing |
| An enterprise customer requires SSO/SCIM | OAuth2/OIDC federation in front of the existing JWT issuance, not a replacement for it |
| Concurrent load approaches the ceiling in `system-design.md` §3 (500 sustained / 2,000 burst sockets) | The upgrade paths already named in `system-design.md` §7 — PgBouncer, Redis Sentinel/Cluster, Kubernetes — not a new paradigm |
