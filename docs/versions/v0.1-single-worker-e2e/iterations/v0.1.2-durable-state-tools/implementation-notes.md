# v0.1.2 Implementation Notes — Durable State & Tools

## Key Decisions

- 2026-08-22 (planning): tools return plain dicts and never ORM objects, so
  the Supervisor's tool schema stays JSON-clean.
- 2026-08-22 (T3): one short `session_scope` per tool call; `append_event`
  flushes but never commits, so the mutation and its audit Event land in
  one atomic transaction (crash between mutation and audit is impossible).
- 2026-08-22 (T4): `update_work_order` is also the creator — first call for
  an id upserts (`work_order.created`), later calls merge
  (`work_order.updated`). No separate create tool; matches the
  delivery-control tool inventory the Supervisor will see.
- 2026-08-22 (T2): `Event.id` switched from uuid string to an autoincrement
  integer — the audit log needs a global append sequence and
  `created_at` ties inside one transaction made ordering unstable.
  Revision 0001 owns this shape; `init_schema()` stays the dev shortcut.
- 2026-08-22 (T6): registry split into `InMemoryWorkerRegistry` (hermetic
  test double) and `PostgresWorkerRegistry` (the new module default),
  same interface. Worker status maps onto `work_orders` columns (added
  `worker_summary`, `worker_error`); observed actions map onto
  `worker.*` Event rows.
- 2026-08-22 (T6): status transitions audit as `worker_status.changed`
  but are excluded from the registry's events view — the v0.1.1
  interface contract says events list observed worker *actions* only.
- 2026-08-22 (T1): test DB strategy — PostgreSQL whenever the compose
  service is reachable (recreates `eds_test` per session), SQLite file
  fallback (WAL + busy_timeout for the worker-thread/poll concurrency)
  otherwise; `EDS_TEST_DATABASE_URL` overrides. Both engines run the
  same SQL layer.
- 2026-08-22 (T5): `deployment_id` persists the stable container name
  (`eds-<work-order>`) so `get_deployment_status` can query it back;
  docker build/run is wrapped in `RetryPolicy` (OSError/RuntimeError
  only — semantic build failures surface immediately).
- 2026-08-22 (T4): terminal semantics — re-issuing the same mark is an
  idempotent no-op; a conflicting mark on a terminal work order raises
  `ValueError`.

## Deviations from Design

- `get_deployment_status` returns the persisted health without a live
  re-probe (kept a pure read; a refresh can be layered on when the A2A
  endpoint needs liveness).
- Tests run on PostgreSQL by default whenever it is reachable, not only
  the "contract" test — the SQLite fallback still covers machines
  without Docker, which the design allows for fast runs.
- Alembic's `env.py` imports `DEFAULT_DATABASE_URL` from
  `control.state` instead of duplicating the connection constant.

## Bugs Encountered

- FK violation on first `update_work_order`: `append_event`'s flush fired
  the `events` INSERT before the pending new `work_orders` row (no ORM
  relationship → no auto-ordering). Fixed by flushing the new row before
  appending the event; same fix in the registry's `_ensure_row`.
- `RetryPolicy.run` off-by-one: the budget was consumed before being
  granted, so `max_retries=2` allowed 2 total attempts instead of 3.
  Fixed to check-then-increment; pinned by a dedicated test.
- Migration test resolved the repo root one directory too high
  (`parents[2]`), so `Config()` silently read nothing ("No
  script_location"). Fixed to `parents[1]`.
- pytest fixture discovery: fixtures defined in `tests/helpers/db.py`
  are not auto-discovered; `tests/conftest.py` re-exports them.

## Lessons Learned

- Flush ordering matters when audit rows reference rows created in the
  same transaction — without an ORM relationship SQLAlchemy cannot order
  the inserts, so flush the parent row explicitly.
- Keeping an in-memory twin of the durable registry made the driver
  refactor nearly free: the interface tests stayed green while the
  backing store changed underneath them.
- An autoincrement integer PK is the cheapest reliable audit sequence;
  timestamps alone cannot order rows committed in one transaction.
- Dogfooding confirmed the acceptance criterion end to end: after the
  runner process exited, a fresh Python process re-read the identical
  `get_current_state` snapshot (complete, 14 events, 2 evidence) from
  PostgreSQL, and the audit trail lists every step from
  `work_order.created` to `work_order.marked_complete`.

Iteration production footprint: ~820 insertions across `tools/`,
`control/`, `db/` (incl. migration), `codex/` and `runner.py`
(estimate was ~450; the dict-serialization surface and the durable
registry account for the difference). Still well within the version
budget.
