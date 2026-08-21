# Work Order State

**Status:** Current · **Component:** `db/models.py`

## 1. Design Goals

PostgreSQL is the durable source of truth. The Supervisor re-reads state each
turn via `get_current_state()` instead of trusting conversation memory
(Principle 4); after a restart, state (plus git candidates, Codex threads and
evidence) is what allows recovery (v0.2/v0.6).

## 2. `work_orders` Table

Grouped per architecture doc §12:

| Group | Columns | Semantics |
|---|---|---|
| identity | `id`, `project_id`, `repository`, `baseline_commit` | what repo, from which base |
| requirement | `original_request`, `confirmed_requirement`, `acceptance_criteria` | raw ask → confirmed spec + criteria |
| worker | `worker_runtime_id`, `worker_thread_id`, `worker_status`, `candidate_commit` | runtime handle + produced candidate |
| inspector | `inspector_runtime_id`, `inspector_thread_id`, `inspector_status`, `inspector_verdict`, `findings` | runtime handle + verdict |
| testing | `testing` (JSON: `pytest` / `api_contract` / `acceptance`) | test surface results |
| deployment | `deployment_status`, `deployment_id`, `deployment_url`, `docs_url`, `deployment_health` | running service facts |
| progress | `gaps`, `artifacts`, `overall_status` | open gaps, artifacts, lifecycle |
| audit | `created_at`, `updated_at` | timestamps |

## 3. `events` Table (append-only audit)

`id · work_order_id · type · payload(JSON) · created_at`. One row per
state-changing Delivery Control call (wired in v0.2). Never updated or
deleted — the audit trail is the observability substrate.

## 4. `evidence` Table

`id · work_order_id · kind · payload(JSON) · created_at` where kind ∈
{`pytest_run`, `inspection`, `deployment_check`, ...}. Evidence is what
completion claims are checked against (Principle 5).

## 5. Lifecycle

```
submitted → working ──▶ completed
              │  ▲
              │  └─ input-required / auth-required (v0.4, resumable)
              ▼
            failed (terminal, reason persisted)
```

- `submitted`: durable row exists (A2A task accepted).
- `working`: Supervisor advancing; worker/inspector/deployment sub-states
  track their own phases.
- `completed`: only via `mark_complete` — all criteria independently verified
  AND deployment live at `/docs`.
- `failed`: only via `mark_failed` — with a persisted reason.

## 6. Schema Evolution

Alembic migrations under `db/migrations/`; the SQLAlchemy models are the
authoritative shape. `gaps`/`findings`/`testing`/`artifacts` are JSON columns
by design — they carry flexible inspection/progress payloads while the
lifecycle columns stay strictly typed.
