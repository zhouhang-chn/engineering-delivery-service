# Delivery Control

**Status:** Current · **Components:** `tools/`, `control/`, `db/`

## 1. Philosophy

Delivery Control does not control the Supervisor — it is what the Supervisor
calls. It provides reliable actions and durable state; it never judges what
should happen next (Principle 2).

## 2. Tool Inventory

| Tool | Module | Semantics |
|---|---|---|
| `get_work_order` | `tools/work_order.py` | full persisted record |
| `update_work_order` | `tools/work_order.py` | field updates (idempotent, audited) |
| `get_current_state` | `tools/work_order.py` | the per-turn snapshot (phase, runtimes, gaps) |
| `mark_complete` | `tools/work_order.py` | terminal: criteria verified + deployment live |
| `mark_failed` | `tools/work_order.py` | terminal: reason persisted |
| `resolve_project` | `tools/project.py` | work order → repository + baseline commit |
| `create_worker_runtime` | `tools/runtime.py` | provision Worker Codex runtime |
| `create_inspector_runtime` | `tools/runtime.py` | provision Inspector Codex runtime |
| `destroy_runtime` | `tools/runtime.py` | teardown (idempotent) |
| `get_worker_status` | `tools/worker.py` | runtime status, thread, candidate state |
| `get_inspector_status` | `tools/inspector.py` | runtime status, verdict, findings |
| `deploy_candidate` | `tools/deployment.py` | build + run candidate, returns deployment id |
| `get_deployment_status` | `tools/deployment.py` | phase, base_url, docs_url, health |
| `record_evidence` | `tools/evidence.py` | persist a verifiable artifact |

## 3. Deterministic Guarantees

- **Durable**: every tool reads/writes the PostgreSQL
  [work order state](work-order-state.md); nothing important lives in memory.
- **Audited**: every state-changing call appends an `Event` row
  (`control/state.py: append_event`) — wired into all tools in v0.2.
- **Evidence-first**: outcomes that matter (pytest runs, verdicts, health
  checks) are persisted via `record_evidence`, not asserted.
- **Idempotent**: lifecycle operations (`destroy_runtime`, deployment
  teardown) are safe to re-issue; retries never corrupt state.
- **Bounded**: retry/timeout policy comes from `control/policy.py`
  (`RetryPolicy`, default max 3 attempts); escalation to a human is a policy
  outcome, not an improvisation.

## 4. Layering

```
tools/          Supervisor-facing: validated, documented, audited
control/        primitives: state access, git operations, policies
db/             SQLAlchemy models + alembic migrations
```

Tools compose primitives; primitives never import tools. Neither layer
contains flow-control decisions — those belong to the
[Supervisor](supervisor.md).
