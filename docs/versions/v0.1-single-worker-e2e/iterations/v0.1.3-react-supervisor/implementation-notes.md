# v0.1.3 Implementation Notes — ReAct Supervisor

## Key Decisions

- 2026-08-22 (planning): a hard turn budget (default 25) converts runaway
  loops into a persisted `mark_failed` instead of an infinite agent run.
- 2026-08-22 (T2): ADK 2.x pinned behavior — the sync `Runner.run` is
  deprecated, so `supervise()` wraps one `asyncio.run` around the whole
  loop and drives `Runner.run_async`; tests stay synchronous.
- 2026-08-22 (T2): "one turn" = one outer loop iteration = one ADK run
  (LLM → tools → … → final text). The agent's internal ReAct chain may
  call several tools per turn; the outer loop re-renders context from
  `get_current_state` before each turn (durable state over memory) and
  appends one `supervisor_turn` audit event per turn with the tool
  calls + decision excerpt.
- 2026-08-22 (T2): the nine v0.1.2 tools are registered directly where
  their signatures are already JSON-clean; five engine-action wrappers
  (`checkout_baseline`, `start_worker_turn`, `run_acceptance_tests`,
  `commit_candidate`, `deploy_candidate`) plus typed
  `update_work_order`(gaps)/`create_worker_runtime` wrappers make the
  agent able to drive the full flow. Wrappers catch exceptions and
  return `{"ok": false, "error": ...}` — ADK 2.x propagates raw tool
  exceptions and would kill the run; structured error returns are what
  make wrong-order recovery possible.
- 2026-08-22 (T2): `deploy_candidate` validates the requested commit
  against the work order's recorded candidate — deploying an invented
  sha (the wrong-order scenario) fails deterministically before docker.
- 2026-08-22 (T2): session-per-work-order via `InMemorySessionService`;
  the ADK session is a cache, PostgreSQL is the truth (supervisor
  design §5). `EDS_LLM_MODEL` env > `DEFAULT_MODEL` (`gemini-2.5-flash`);
  tests inject a `BaseLlm` double directly.
- 2026-08-22 (T3): worker polling stays LLM-driven (`get_worker_status`
  tool calls); the ScriptedLlm test double polls reactively off the
  durable status so thread timing never makes tests racy.

## Deviations from Design

- Design listed "the nine M1 tools" only; the supervisor additionally
  needed the five engine-action wrappers above to be genuinely
  autonomous. They are thin, deterministic executors — the *decision*
  stays with the agent, so the architecture principle holds.
- T5 real-model leg: the marked live test exists
  (`tests/test_live_supervisor.py::test_live_supervisor_real_llm_delivers`)
  but skips — no LLM credentials in this environment (no
  `GOOGLE_API_KEY`, no Vertex ADC). The everything-real-except-model
  leg (real PostgreSQL + real Docker build/run/health + `/docs` probe +
  ScriptedWorker + scripted LLM) passes as `-m docker`. The real-model
  run is carried into v0.1.4 dogfooding, where the A2A endpoint
  exercises the same `supervise()` path.

## Bugs Encountered

- `SupervisorToolConfig` initially declared `worker=None` without a
  type annotation — dataclass fields require annotations, so `worker`
  was silently a class attribute and `configure_supervisor(worker=...)`
  raised `TypeError`. Fixed by annotating all fields.
- First live docker run came back `unhealthy`: the live worker script
  rewrote `app/main.py` without the root `/` endpoint, and the health
  check probes `/` and `/docs`. The contract fixture keeps `/`; the
  live script now does too.
- First live-docker test version removed the deployed container in a
  `finally` before probing `docs_url` — probe then cleanup, not the
  other way round.

## Lessons Learned

- ADK 2.x moved `google.adk.llm` → `google.adk.models` and renamed
  `Runner.run(content=...)` → `new_message=`; a 10-line smoke script
  against the installed package settled the API surface faster than
  docs.
- ADK function tools propagate exceptions by default (no error
  function-response); any agent-facing wrapper that should be
  recoverable must convert failures itself.
- A reactive test double (poll durable state until terminal, then
  continue the script) is the pattern for testing agent loops against
  real async work without sleeps or flakiness.
