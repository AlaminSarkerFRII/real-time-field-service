# FieldSync — Repository Structure

**Companion docs:** [`architecture.md`](./architecture.md) · [`system-design.md`](./system-design.md) · [`data-model.md`](./data-model.md) · [`data-flow-diagram.md`](./data-flow-diagram.md) · [`tech-stack.md`](./tech-stack.md)

The concrete, file-by-file layout that makes the rules in the other five documents impossible to accidentally violate — not just a folder sketch. If a file's location in this tree doesn't match its stated job, that's a bug in the layout, not a style nit.

## Layout principles

- **One codebase, apps by domain.** `web`, `worker`, and `beat` (per `system-design.md` §4) are the same image, running the same code, differing only by start command — there is no separate real-time or worker repo to keep in sync.
- **Views and consumers are thin.** They parse the request, check permission, and call one function in `services.py`. Neither ever writes to the ORM directly for a state-changing operation — that's the "one write path" rule from `architecture.md` §5, enforced here by *where the write is allowed to live*, not by convention alone.
- **Every process in `data-flow-diagram.md` maps to exactly one function.** The table at the end of this document is the authoritative pointer from DFD process number to file and function name.
- **Tests mirror app structure.** A file at `apps/jobs/services.py` has its tests at `apps/jobs/tests/test_services.py` — no separate top-level `tests/` tree to fall out of sync with the code it covers.

## Annotated tree

```
fieldsync/
├─ config/                        # the project: settings, wiring, no business logic
│   ├─ settings/
│   │   ├─ base.py                # shared settings — installed apps, REST_FRAMEWORK, SIMPLE_JWT, CHANNEL_LAYERS
│   │   ├─ dev.py                 # DEBUG=True, local CORS, verbose logging
│   │   ├─ prod.py                # secrets from env (django-environ), Sentry init, allowed hosts
│   │   └─ test.py                # fast password hasher, in-memory channel layer for CI
│   ├─ asgi.py                    # ProtocolTypeRouter: http → Django/DRF, websocket → JWT auth middleware → URLRouter
│   ├─ celery.py                  # Celery app instance + beat schedule (reminders, sweep, nightly report)
│   ├─ urls.py                    # /api/... include()s per app, /api/docs/ (drf-spectacular), /healthz, /readyz
│   └─ routing.py                 # websocket_urlpatterns: /ws/dispatch/, /ws/agent/, /ws/jobs/<id>/
│
├─ apps/
│   ├─ common/                    # cross-cutting code with no domain of its own
│   │   ├─ permissions.py         # IsDispatcher, IsAssignedAgent, IsJobParticipant — role checks, per system-design.md §6 L3
│   │   ├─ querysets.py           # OrgScopedQuerySet / OrgScopedManager — the one place organization_id filtering lives (data-model.md, multi-tenancy)
│   │   ├─ pagination.py          # shared cursor/page-number pagination for list endpoints
│   │   ├─ middleware.py          # request_id + structured logging context (system-design.md §8.1 fields)
│   │   ├─ health.py              # /healthz (liveness), /readyz (DB + Redis ping) — system-design.md §7.1
│   │   └─ realtime.py            # thin group_send wrapper: send_to_group(group, type, payload) — the one call site every service imports (DFD process 3.0)
│   │
│   ├─ accounts/                  # identity: who someone is, not what they can do in a job
│   │   ├─ models.py              # User (custom, role field), AgentProfile (1–1 extension)
│   │   ├─ serializers.py         # UserSerializer, MeSerializer, TokenObtainPairSerializer subclass
│   │   ├─ views.py               # /api/auth/token/, /api/auth/token/refresh/, /api/me/
│   │   ├─ services.py            # update_agent_status(), record_location() — the only writer of AgentProfile
│   │   ├─ ws_auth.py             # JWTAuthMiddleware — reads the token off the WS connect, attaches scope["user"]
│   │   └─ tests/
│   │
│   ├─ jobs/                      # the core domain: Job, its lifecycle, and everything that reacts to it
│   │   ├─ models.py              # Job, JobEvent, Notification
│   │   ├─ state_machine.py       # the {status: {allowed_next}} dict + transition validator — architecture.md §4
│   │   ├─ serializers.py         # JobSerializer, JobEventSerializer, NotificationSerializer
│   │   ├─ views.py               # JobViewSet — list/create/retrieve + assign()/status() actions, all delegate to services.py
│   │   ├─ services.py            # create(), assign(), transition() — DFD process 1.0, the single source of truth every writer calls
│   │   ├─ consumers.py           # DispatchConsumer, AgentConsumer, JobConsumer (JobConsumer mixes in chat.ConsumerMixin — see apps/chat)
│   │   ├─ tasks.py               # notify_status_change, send_upcoming_reminders, expire_stale_locations, daily_ops_report — DFD processes 5.0/6.0
│   │   ├─ permissions.py         # job-specific object-level checks that build on apps/common/permissions.py
│   │   └─ tests/
│   │       ├─ test_state_machine.py
│   │       ├─ test_services.py
│   │       ├─ test_views.py           # DRF APIClient — REST contract
│   │       ├─ test_consumers.py       # WebsocketCommunicator — WS contract
│   │       └─ test_tasks.py           # Celery eager-mode + idempotency assertions
│   │
│   ├─ chat/                      # per-job conversation, deliberately the smallest app
│   │   ├─ models.py              # ChatMessage
│   │   ├─ serializers.py         # ChatMessageSerializer
│   │   ├─ services.py            # post_message() — checks participant membership, then writes — DFD process 4.0
│   │   ├─ consumers.py           # ChatConsumerMixin — handlers for chat.message, composed into jobs.consumers.JobConsumer
│   │   └─ tests/
│   │
│   └─ realtime/                  # protocol plumbing shared by every consumer — no domain models
│       ├─ middleware.py          # WS connection-level plumbing (ping/pong, close codes) layered under accounts/ws_auth.py
│       ├─ groups.py              # group name builders: org_group(id), job_group(id), user_group(id) — one place these strings are ever constructed
│       └─ tests/
│
├─ frontend/                      # thin HTML + JS — no build step
│   ├─ dispatcher/                # live map (Leaflet) + job list
│   ├─ agent/                     # assigned job + location-ping simulator + chat
│   └─ customer/                  # single job status + chat
│
├─ deploy/
│   ├─ Dockerfile                 # multi-stage: build stage (compilers, deps) → slim runtime stage, non-root user
│   └─ nginx.conf                 # TLS termination, proxy_pass + WS upgrade headers → web:8000
│
├─ docker-compose.yml             # web · worker (realtime queue) · worker-reports · beat · db · redis · nginx — run from repo root
├─ docker-compose.prod.yml        # overrides: no live-reload, resource limits, restart policies
│
├─ .github/
│   └─ workflows/
│       └─ ci.yml                 # ruff → mypy → pytest (incl. WS + Celery-eager tests) → build image → (on tag) push
│
├─ scripts/
│   ├─ seed.py                    # fixtures: orgs, users per role, a handful of jobs in different states
│   └─ wait_for.py                # used by compose entrypoints to block on db/redis before migrate/start
│
├─ pyproject.toml                 # dependencies, ruff config, mypy config, pytest config — tech-stack.md §2
├─ .pre-commit-config.yaml        # ruff + mypy on commit
├─ .env.example                   # documents every required env var; the real .env is never committed
└─ README.md                      # architecture diagram + run instructions, links into docs/
```

## Layering rules, made explicit

| Rule | Enforced by |
|---|---|
| A view or consumer never calls `Model.objects.create/update/delete` directly for a domain write | Code review + the fact that `services.py` is the only module importing the model for writes; a lint rule can flag ORM writes outside `services.py` if this starts drifting |
| Every queryset used in a list/detail view starts from an org-scoped manager | `apps/common/querysets.py` is the only place `organization_id` filtering is implemented — a view that bypasses it has to visibly import the raw model manager instead |
| A `group_send` call never happens from anywhere but `apps/common/realtime.py`'s wrapper | One function signature, `send_to_group(group, type, payload)`, used by `jobs/services.py`, `chat/services.py`, and `jobs/tasks.py` alike — this is DFD process 3.0 having exactly one call site |
| Celery tasks never contain business logic, only orchestration | `jobs/tasks.py` functions are short: fetch what's due, call a `services.py` function per row, handle retries — the actual state change is identical to what the REST view would do |
| A test file's path mirrors the source file it tests | `apps/jobs/tests/test_services.py` next to `apps/jobs/services.py`, not a parallel `tests/jobs/` tree |

## DFD process → code, in full

Expands the summary table in `data-flow-diagram.md` to the actual file and function.

| DFD # | Process | File | Function |
|---|---|---|---|
| 1.0 | Manage Jobs | `apps/jobs/services.py` | `create()`, `assign()`, `transition()` |
| 2.0 | Track Location | `apps/accounts/services.py` | `record_location()`, called from `apps/jobs/consumers.py::AgentConsumer.receive()` |
| 3.0 | Broadcast Live Update | `apps/common/realtime.py` | `send_to_group(group, type, payload)` |
| 4.0 | Chat | `apps/chat/services.py` | `post_message()` |
| 5.0 | Notify | `apps/jobs/tasks.py` | `notify_status_change()` |
| 6.0 | Scheduled Sweep & Reports | `apps/jobs/tasks.py` | `send_upcoming_reminders()`, `expire_stale_locations()`, `daily_ops_report()` |

## Two structural decisions worth flagging

**Why `AgentProfile` and `record_location()` live in `accounts/`, not `jobs/`.** `AgentProfile` is a User extension (`data-model.md`), not a Job-owned table — a location ping updates the agent regardless of which job, if any, is currently assigned. Keeping it in `accounts/` means `jobs/` never needs to import agent-identity concerns to do its own job, only the reverse.

**Why chat handlers are a mixin, not a separate consumer.** `architecture.md` §6 routes both status updates and chat through one socket — `/ws/jobs/<id>/`. Rather than duplicating that connection's auth and group-join logic in two places, `JobConsumer` in `apps/jobs/consumers.py` composes in `ChatConsumerMixin` from `apps/chat/consumers.py`. One socket, one consumer class, domain code still split by app.
