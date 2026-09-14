# FieldSync — Documentation

Real-time dispatch platform for small field-service businesses (plumbing, HVAC, appliance repair). Dispatchers watch agents move on a live map, everyone sees job status change the instant it happens, and customers chat with the agent on the way.

## Reading order

| # | Document | Status | Covers |
|---|----------|--------|--------|
| 1 | [`architecture.md`](./architecture.md) | done | The system end to end: actors, container diagram, real-time event flow, REST/WS contracts, background jobs, repo layout, and the 4-week build plan |
| 2 | [`system-design.md`](./system-design.md) | done | Production posture on top of (1): goals/non-goals, SLOs, scaling topology, security layers, observability, and a tracked risk register |
| 3 | [`data-model.md`](./data-model.md) | done | ER diagram formalizing the nine core tables, constraints/indexes, and the multi-tenancy enforcement rule |
| 4 | [`data-flow-diagram.md`](./data-flow-diagram.md) | done | Level 0/1 DFD — how data moves between the six core processes and the seven data stores, and where each process lives in the repo |
| 5 | `repo-structure.md` | pending | The concrete app/module layout that enforces the service-layer discipline from (1)–(2) and implements the processes in (4) |

Start with `architecture.md` for the shape of the system, then `system-design.md` for what it takes to run it in production, then `data-model.md` and `data-flow-diagram.md` for the structure and movement of the data itself. Doc (5) will implement all of the above in code — it doesn't duplicate content that belongs here.
