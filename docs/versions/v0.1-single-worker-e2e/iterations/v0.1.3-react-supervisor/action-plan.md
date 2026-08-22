# v0.1.3 Action Plan — ReAct Supervisor

- [x] T1 — Test-First: supervisor contract test with fake LLM (red)
- [x] T2 — Implement `build_supervisor()` + tool registration + env-based
      model config
- [x] T3 — Implement the supervise run-loop with turn budget and
      `supervisor_turn` events
- [x] T4 — Contract tests green (happy path + wrong-order recovery +
      budget exhaustion)
- [x] T5 — Live run (marked): real LLM + ScriptedWorker reaches
      `mark_complete` with a deployment record — real-infra leg
      (`-m docker`: real PostgreSQL + Docker build/run + health +
      `/docs` probe) green; the real-model leg (`-m llm`) exists but
      skips without LLM credentials in this environment (see
      implementation notes; carried to v0.1.4 dogfooding)
- [x] T6 — Prompt tuning pass from observed events; update
      `agent/prompts/supervisor_system.md` and notes — prompt rewritten
      around the actual tool inventory, delivery order, wrong-order
      recovery and stop conditions; real-model tuning pending
      credentials (v0.1.4)

Acceptance: supervisor autonomously completes a ScriptedWorker work order;
failures land in `mark_failed` with reasons; every turn auditable.
