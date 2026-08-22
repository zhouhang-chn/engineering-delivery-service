# v0.1.2 Design — Durable State & Tools

Implements version design D4 plus the audit/evidence guarantees from
[delivery-control design](../../../designs/delivery-control.md).

## Persistence

- `control/state.py`: `make_engine(EDS_DATABASE_URL)`, session factory,
  `append_event` (already sketched). Alembic initialized with the current
  models as revision 0001; `init_schema()` stays for dev/test convenience.
- Tests run against PostgreSQL via docker compose; a SQLite fallback engine
  is allowed for fast unit runs (JSON columns degrade gracefully) —
  contract tests always use PostgreSQL.

## Tools (`tools/`)

Each tool: validate input → mutate within a session → `append_event` →
return a plain dict (JSON-serializable, no ORM objects). The worker
status registry moves from memory to `work_orders.worker_status` +
`events` rows; runtime/deploy calls wrap external operations with
`RetryPolicy` (bounded, no semantic retries).

## Runner rewiring

`runner.py` keeps its step order but calls tools only
(`update_work_order`, `create_worker_runtime`, `get_worker_status`,
`deploy_candidate`, `record_evidence`, `mark_complete`). Restart between
steps must show the same facts via `get_current_state`.
