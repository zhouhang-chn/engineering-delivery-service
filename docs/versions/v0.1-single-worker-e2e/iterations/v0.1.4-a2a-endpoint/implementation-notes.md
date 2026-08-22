# v0.1.4 Implementation Notes — A2A Endpoint & Close-out

## Key Decisions

- 2026-08-22 (planning): supervisor runs as a background task per work
  order inside the service process; a real job queue is v0.2+ scope.
- 2026-08-22 (T2): the A2A wire surface is implemented as a thin
  FastAPI JSON-RPC adapter (`message/send`, `tasks/get`,
  `/.well-known/agent-card.json`) over the tools — task state always
  re-derived from `get_current_state`, never cached in memory. A2A Task
  id == work order id, so any caller can cross-check the durable
  snapshot directly.
- 2026-08-22 (T2): `start_supervised_delivery` is the single shared
  launcher (CLI joins the thread; the endpoint returns immediately).
  It MERGES the active supervisor config instead of replacing it, so
  pre-configured doubles/URLs survive a launch.
- 2026-08-22 (T2): state mapping — `complete`→`completed` (artifacts
  attached), `failed`→`failed` (persisted reason as status message),
  `in_progress`→`working`, unknown future statuses degrade to `working`
  (never to a false terminal). `submitted` is mapped (`None` overall
  status) but not produced in M1: creation sets `in_progress`.
- 2026-08-22 (T2): artifacts per a2a-interface §4 — `repository`@
  commit, `deployment_url`, `docs_url`, `pytest_evidence` (latest
  pytest_run payload), `delivery_summary` (completion artifact).
  Inspection artifact arrives with v0.3.
- 2026-08-22 (T2): error mapping — unknown method → -32601, unknown
  task → -32001, empty requirement → a `failed` task object with
  reason (per design "invalid requirement → task failed"), parse
  errors → -32700.

## Deviations from Design

- Design said "a2a_api/server.py builds an a2a-sdk application". The
  installed `a2a-sdk` resolved to the 1.x proto-first rewrite whose
  server stack (`DefaultRequestHandlerV2`, proto `TaskStore`, queue
  manager) fights the architecture's "task state derives from durable
  PostgreSQL" rule — the SDK's TaskStore bookkeeping would hold proto
  snapshots in memory. The endpoint therefore implements the A2A
  JSON-RPC wire contract directly (agent card, message/send, tasks/get,
  JSON-RPC error codes). The SDK stays a dependency (types, client
  surface, `a2a-sdk[http-server]` extras). The protocol contract, not
  the SDK class hierarchy, was the design's substance.
- T3's "real Codex" leg: the marked full-chain test
  (`test_a2a_full_chain_real_llm_and_codex`, `-m 'llm and codex'`)
  exists but skips — no LLM credentials in this environment. The
  everything-real-except-model leg passed: real uvicorn HTTP endpoint,
  raw httpx A2A call, real PostgreSQL, real Docker build/run/health,
  live `/docs` + Swagger verification + `/hello` probe (`-m docker`).
- T6/T7 (version close-out: gate, retrospect, milestones, PR) execute
  after v0.1.5 per the version-level plan; they cannot pass the gate
  while version tasks remain open.

## Bugs Encountered

- `start_supervised_delivery` initially called `configure_supervisor`
  with only its own kwargs, silently wiping `repo_url`/`llm_factory`
  configured by tests — the scripted LLM was replaced by the real
  Gemini model, every supervisor turn failed with "No API key", and
  the task ended in budget exhaustion. Fixed by merging with the
  current config before reconfiguring.
- First dogfood evidence write failed on a non-JSON-serializable
  httpx `URL` object in the payload; evidence payloads must be plain
  JSON dicts.

## Lessons Learned

- When a launcher both reads and writes process-global config, replace
  semantics lose pre-set fields; merge semantics (explicit field
  resolution) is the safe pattern.
- A thin protocol adapter over durable tools made the endpoint
  trivially testable with `TestClient` and trivially dogfoodable over
  real HTTP — no session/queue plumbing to double.
- Check the installed SDK generation before designing against it: the
  a2a-sdk 0.2-era pydantic API we planned on became a proto-first
  rewrite at resolution time (`>=0.2.0` allowed 1.1.2).
