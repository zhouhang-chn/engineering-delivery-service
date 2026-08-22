# v0.1.2 Action Plan — Durable State & Tools

- [x] T1 — Test-First: tool unit tests against PostgreSQL (create/update/
      get_current_state/mark_*) that fail against the stubs
- [x] T2 — Alembic init + initial migration from current models; document
      dev workflow (`docker compose up -d postgres`, `alembic upgrade head`)
- [x] T3 — Implement `control/state.py` session plumbing + `append_event`
      wiring into every state-changing tool
- [x] T4 — Implement work-order tools (CRUD, current state, mark_complete/
      mark_failed) — T1 green
- [x] T5 — Implement runtime/deployment/evidence tools with `RetryPolicy`
      on external calls; unit tests green
- [x] T6 — Move worker status registry to PostgreSQL; restart-mid-flow
      test proves facts survive (create → simulate crash → re-read state)
- [x] T7 — Rewire `runner.py` onto tools; full contract test green;
      update iteration + version notes

Acceptance: all M1 tools real and tested; every mutation emits an event;
runner flow unchanged from outside; restart shows identical
`get_current_state` output.
