# System Architecture

**Status:** Current · **Source:** architecture draft v0.2 (docs/refer/)

## 1. Positioning

Engineering Delivery Service (EDS) is an autonomous engineering delivery
service exposed to agents and enterprise systems. It receives a complete
**Engineering Work Order** — not a coding prompt — and drives it autonomously:

```
API Requirement → Requirement Confirmation → Development → Testing
                → Inspection → Deployment → Acceptance
```

MVP scope (lifted only by the milestone plan):

- Python + FastAPI delivery only
- single Git repository per work order
- explicit API requirement with acceptance criteria
- automated testing (pytest)
- containerized execution, deployed to a test environment
- human acceptance via the delivered `/docs` (Swagger UI)

EDS exposes an [A2A](a2a-interface.md) interface; internally a free-running
[ReAct Supervisor](supervisor.md) drives the work via
[Delivery Control tools](delivery-control.md) until the work order reaches its
goal state.

## 2. Core Principles

1. **Supervisor owns the delivery.** The top-level controller is a free-running
   ReAct Supervisor. There is deliberately no deterministic workflow layer
   above it — flow control belongs to the Supervisor.
2. **Delivery Control is deterministic.** `tools/` and `control/` provide
   reliable state and actions (CRUD, lifecycle, retry/timeout primitives,
   audit). They never decide "what should happen next".
3. **Worker produces the candidate; Inspector establishes the truth.** Worker
   "done" only means the candidate is ready for inspection — never that the
   work order is complete. The Inspector verifies independently and never
   modifies the candidate. Worker and Inspector never communicate directly.
4. **Durable state over conversation memory.** Every decision input (current
   state, open gaps, evidence) is persisted in PostgreSQL
   ([work order state](work-order-state.md)) and re-read via tools each turn.
5. **Evidence-based acceptance.** Completion claims require persisted evidence
   — pytest results, inspection verdicts, deployment health — not agent
   assertions.
6. **End-to-end runnable at every version.** Each milestone keeps the full
   chain `Requirement → Development → Testing → Deployment → /docs` working;
   later versions add autonomy and reliability, never a partial pipeline.
7. **MVP scope discipline.** FastAPI only, single repository, until the
   milestone plan explicitly lifts the constraint.

## 3. Component Model

```
                  External Agent / Platform / User
                              │ A2A
                              ▼
                 ┌───────────────────────────┐
                 │ Engineering Delivery Agent│  a2a_api/
                 │ Google ADK · ReAct        │  agent/
                 │ Supervisor                │
                 └─────────────┬─────────────┘
                               │ reason → tool → observe
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Delivery Control │ │ Worker Runtime   │ │ Inspector Runtime│
│ tools/ control/  │ │ codex/ (writable │ │ codex/ (clean    │
│ PostgreSQL state │ │ sandbox)         │ │ sandbox)         │
└─────────┬────────┘ └────────┬─────────┘ └────────┬─────────┘
          │        candidate commit    verdict
          └────────────────────┼────────────────────┘
                               ▼
                       Deployment Runtime (deployment/)
                               ▼
                        FastAPI `<base>/docs`
```

Responsibility summary:

| Component | Owns | Never does |
|---|---|---|
| Supervisor | understand, decide, coordinate, recover, finish | edit code, run tests, debug |
| Delivery Control | state, lifecycle, audit, idempotent actions | decide what happens next |
| Worker | candidate commit + engineering summary + test evidence | declare the work order complete |
| Inspector | verdict, verified/failed criteria, evidence, risk | modify the candidate |
| Deployment | build, run, health, expose `/docs` | judge acceptance criteria |

## 4. Technology Stack

| Layer | Choice |
|---|---|
| External protocol | A2A (`a2a-sdk`; local package is `a2a_api/` to avoid import shadowing) |
| Supervisor framework | Google ADK |
| Supervisor pattern | free-running ReAct agent |
| Deterministic control | Delivery Control tools |
| Durable state | PostgreSQL (SQLAlchemy + alembic) |
| Worker / Inspector | Codex App Server threads in separate sandboxes |
| Project source | Git |
| API framework (delivered) | FastAPI only |
| Tests (delivered) | pytest |
| API contract (delivered) | OpenAPI |
| Deployment | Docker (local, test environment) |
| Human acceptance | FastAPI `/docs` |
| Delivery artifact | commit → PR (from v0.5) |
| Observability | Work Order events + Codex events |
| Build tooling | uv |

## 5. Code Layout

```
agent/        ReAct Supervisor + prompts
a2a_api/      A2A endpoint (Task ≈ Engineering Work Order)
tools/        Delivery Control tools exposed to the Supervisor
control/      Deterministic state / git / policy primitives
codex/        Codex App Server client + worker/inspector drivers
sandbox/      Sandbox lifecycle (writable worker, clean inspector)
deployment/   Docker deployment runtime
db/           SQLAlchemy models + alembic migrations
docs/         designs/ (this doc set), refer/ (source draft), milestones.md
```

There is deliberately no `workflow/` package: a deterministic pipeline would
violate Principle 1. `control/` only provides state and action primitives.

## 6. Milestone Plan

See [../milestones.md](../milestones.md): v0.1 (single worker end-to-end) →
v0.2 (durable delivery control) → v0.3 (independent inspector) →
v0.4 (requirement confirmation + HITL) → v0.5 (project-aware delivery) →
v0.6 (recoverable autonomous delivery). Every milestone ships the full
end-to-end chain (Principle 6).
