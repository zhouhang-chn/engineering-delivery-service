# v0.1.3 Action Plan — ReAct Supervisor

- [ ] T1 — Test-First: supervisor contract test with fake LLM (red)
- [ ] T2 — Implement `build_supervisor()` + tool registration + env-based
      model config
- [ ] T3 — Implement the supervise run-loop with turn budget and
      `supervisor_turn` events
- [ ] T4 — Contract tests green (happy path + wrong-order recovery +
      budget exhaustion)
- [ ] T5 — Live run (marked): real LLM + ScriptedWorker reaches
      `mark_complete` with a deployment record
- [ ] T6 — Prompt tuning pass from observed events; update
      `agent/prompts/supervisor_system.md` and notes

Acceptance: supervisor autonomously completes a ScriptedWorker work order;
failures land in `mark_failed` with reasons; every turn auditable.
