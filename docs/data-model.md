# FieldSync — Data Model (ER Diagram)

**Companion docs:** [`architecture.md`](./architecture.md) · [`system-design.md`](./system-design.md) · [`data-flow-diagram.md`](./data-flow-diagram.md) · `repo-structure.md` (pending)

This formalizes the entities sketched in `architecture.md` §4 into a concrete relational schema: cardinalities, keys, constraints, and indexes. It's the structural view — for how data *moves* between these tables at runtime, see the companion [Data Flow Diagram](./data-flow-diagram.md).

## Why nine tables

`architecture.md` counts **nine tables**: the seven domain entities below, plus two auth-infrastructure tables that `djangorestframework-simplejwt`'s blacklist app creates automatically — `OutstandingToken` and `BlacklistedToken` — which back the refresh-token revocation described in `system-design.md` §6 (L2 · AuthN) and risk R-2. They're included here because they're real rows in the same Postgres database, even though no application code queries them directly.

## Entity-relationship diagram

```mermaid
erDiagram
    ORGANIZATION ||--o{ USER : employs
    ORGANIZATION ||--o{ JOB : scopes
    USER ||--o| AGENTPROFILE : "extends (agent only)"
    USER ||--o{ JOB : "books (as customer)"
    USER ||--o{ JOB : "is assigned (as agent)"
    JOB ||--o{ JOBEVENT : logs
    USER ||--o{ JOBEVENT : performs
    JOB ||--o{ CHATMESSAGE : contains
    USER ||--o{ CHATMESSAGE : sends
    USER ||--o{ NOTIFICATION : receives
    USER ||--o{ OUTSTANDINGTOKEN : issues
    OUTSTANDINGTOKEN ||--o| BLACKLISTEDTOKEN : "revoked via"

    ORGANIZATION {
        uuid id PK
        string name
        string timezone
        datetime created_at
    }
    USER {
        uuid id PK
        string email UK
        string password_hash
        string role "dispatcher | agent | customer"
        string full_name
        uuid organization_id FK
        boolean is_active
        datetime created_at
    }
    AGENTPROFILE {
        uuid user_id PK_FK
        string status "online | offline | busy"
        decimal last_lat
        decimal last_lng
        datetime last_ping_at
        string_array skills
    }
    JOB {
        uuid id PK
        string reference UK "unique per organization"
        string status "state machine, see architecture.md §4"
        string priority "low | normal | urgent"
        string address
        decimal lat
        decimal lng
        datetime scheduled_for
        uuid customer_id FK
        uuid agent_id FK "nullable until assigned"
        uuid organization_id FK "authoritative tenant boundary"
        datetime created_at
        datetime updated_at
    }
    JOBEVENT {
        uuid id PK
        uuid job_id FK
        string from_status
        string to_status
        uuid actor_id FK
        datetime created_at
    }
    CHATMESSAGE {
        uuid id PK
        uuid job_id FK
        uuid sender_id FK
        text body
        datetime created_at
    }
    NOTIFICATION {
        uuid id PK
        uuid recipient_id FK
        string kind "assigned | arriving | …"
        string title
        text body
        datetime read_at "nullable"
        datetime created_at
    }
    OUTSTANDINGTOKEN {
        bigint id PK
        uuid user_id FK
        string jti UK
        datetime created_at
        datetime expires_at
    }
    BLACKLISTEDTOKEN {
        bigint id PK
        bigint token_id FK
        datetime blacklisted_at
    }
```

## Entity notes

| Entity | Purpose | Design decision worth flagging |
|---|---|---|
| **Organization** | Tenant boundary | Every other domain table roots back to one, directly or transitively — see [multi-tenancy](#multi-tenancy-enforcement) below |
| **User** | Auth + identity for all three roles | One table, not three — `role` is a column, not a subclass, so a permission check is always one field read, never a type check |
| **AgentProfile** | Agent-only extension of User | Modeled as a strict 1–1 extension rather than adding location columns to `User`, so dispatcher/customer rows never carry meaningless nulls |
| **Job** | The hub entity | Carries its own `organization_id` even though it's derivable via `customer` or `agent` — see below |
| **JobEvent** | Append-only audit trail | Never updated or deleted; a `Job.status` change without a matching `JobEvent` row is a bug, not a valid state |
| **ChatMessage** | Per-job conversation | No `read_at` / edit / delete in v1 — chat is intentionally the simplest table, per the scope-cut order in `architecture.md` §11 |
| **Notification** | Per-user inbox | Decoupled from delivery — a row exists whether or not the email/SMS send in the same Celery task actually succeeded |
| **OutstandingToken / BlacklistedToken** | Refresh-token lifecycle | Persisted (not just the Redis deny-list) so revocation survives a Redis flush — narrows risk R-2, doesn't eliminate it |

## Multi-tenancy enforcement

`Job.organization_id` is stored directly rather than derived by joining through `customer` or `agent`, for two reasons that matter more as the system grows:

1. **A job can be unassigned** (`agent_id` is null between `new` and `assigned`) — there'd be no path to the organization through the agent at all during that window.
2. **Every tenant-scoped queryset filters on one column, on one table, with one index** — `Job.objects.filter(organization_id=...)` — rather than requiring a join to be present and correct in every view. This is the column the base queryset mixin referenced in `system-design.md` §6 (L3 · AuthZ) actually filters on.

The same reasoning extends to `ChatMessage` and `JobEvent`: both are scoped in queries through their `job_id` foreign key rather than a duplicated `organization_id`, because they have no independent existence — a chat message or an event is *only* ever fetched in the context of a specific job the caller has already been authorized against.

## Constraints & indexes

| Table | Constraint / index | Reason |
|---|---|---|
| `user` | `UNIQUE(email)` | Login identity |
| `job` | `UNIQUE(organization_id, reference)` | Reference codes are human-facing and only need to be unique per business, not globally |
| `job` | `INDEX(organization_id, status)` | Backs the dispatcher's filtered job list — the single most frequent query in the system |
| `job` | `INDEX(agent_id, status)` | Backs "my assigned jobs" for the agent role |
| `jobevent` | `INDEX(job_id, created_at)` | Backs the `/api/jobs/{id}/events/` audit-trail endpoint, always fetched in time order |
| `chatmessage` | `INDEX(job_id, created_at)` | Backs paginated chat history; matches the access pattern exactly |
| `agentprofile` | `INDEX(last_ping_at)` | Backs the `expire_stale_locations` sweep, which scans for stale rows on a schedule |
| `notification` | `INDEX(recipient_id, read_at)` | Backs the unread-count query without a table scan |
| `outstandingtoken` | `UNIQUE(jti)` | One row per issued token, matched by its JWT ID claim |

## Job status, as it constrains this schema

`Job.status` is a fixed enumeration, not a free string — `new`, `assigned`, `en_route`, `on_site`, `completed`, `cancelled` — validated by the state machine in `architecture.md` §4, not by a database check constraint, so an illegal transition raises a clear application error instead of a opaque constraint violation. `JobEvent.from_status` / `to_status` record every transition the state machine allowed, which is what makes the audit trail and the state machine two views of the same guarantee rather than two places the rule could drift apart.
