# v0.1 Implementation Notes — Single Worker End-to-End

Written during implementation; one entry per completed task. Iteration-level
detail lives in each iteration's own `implementation-notes.md`.

## Key Decisions

- 2026-08-22 (planning): four iterations ordered by risk — engine (Codex +
  sandbox + deploy) before durable tools, before Supervisor, before A2A —
  so the riskiest unknown (Codex App Server binding) is spiked first.
- 2026-08-22 (planning): v0.1 sandbox is a local directory per role under
  `EDS_WORK_DIR`; container-backed isolation is deferred (design D1).
- 2026-08-22 (planning): worker turns run asynchronously and tools poll
  status — the Supervisor never blocks in one tool call (design D2).
- 2026-08-22 (planning): user test surface is a CLI (an external A2A
  client), not a web UI — dogfooding doubles as a contract test, and the
  no-frontend-in-MVP principle keeps EDS's own UI out of scope (v0.1.5).
- 2026-08-22 (v0.1.2): one short DB session per tool call; a mutation
  and its audit Event commit atomically. `update_work_order` doubles as
  the creator (upsert). Audit `Event.id` is an autoincrement integer so
  the append order is stable across engines.
- 2026-08-22 (v0.1.2): worker registry is durable (`work_orders`
  columns + `worker.*` events); an in-memory twin keeps driver unit
  tests hermetic behind the same interface.
- 2026-08-22 (v0.1.3): supervisor turn = one ADK run (multi-tool ReAct
  chain allowed); the outer loop re-renders context from durable state,
  audits one `supervisor_turn` event per turn, and a budget of 25 turns
  bounds runaway loops into `mark_failed`.
- 2026-08-22 (v0.1.3): agent-facing tool wrappers convert exceptions to
  `{"ok": false, "error": ...}` results — ADK 2.x propagates raw tool
  exceptions, which would abort the agent run instead of letting it
  recover.
- 2026-08-22 (v0.1.4): the A2A endpoint is a thin JSON-RPC adapter over
  the tools; A2A Task id == work order id and task state is re-derived
  from durable state on every `tasks/get`. The a2a-sdk server stack
  (proto-first 1.x) was bypassed — its in-memory TaskStore bookkeeping
  contradicts "task state derives from PostgreSQL" (details in the
  iteration notes).

## Deviations from Design

None at the version level so far; deviations inside an iteration are
recorded in that iteration's own implementation-notes.md.

## Bugs Encountered

None at the version level so far; bugs found and fixed inside an
iteration are recorded in that iteration's implementation-notes.md.

## Lessons Learned

- 2026-08-22 (v0.1.2): audit rows referencing rows created in the same
  transaction need an explicit parent flush — without an ORM
  relationship SQLAlchemy cannot order the inserts (FK violation
  otherwise).
