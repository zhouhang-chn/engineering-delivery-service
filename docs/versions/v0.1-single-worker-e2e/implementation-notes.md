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

## Deviations from Design

None yet.

## Bugs Encountered

None yet.

## Lessons Learned

None yet.
