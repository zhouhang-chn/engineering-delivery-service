# v0.1 Design — Single Worker End-to-End

**Version:** v0.1-single-worker-e2e

## 1. Component View (v0.1 slice — no Inspector)

```
A2A caller ──▶ a2a_api/server.py (thin adapter)
                     │ creates/reads Work Order via tools
                     ▼
              agent/supervisor.py  (ADK LlmAgent, ReAct)
                     │ function tools (poll-based, never blocking)
                     ▼
        tools/*  ──▶  db/models.py (PostgreSQL, M1 field subset)
          │
          ├─▶ codex/worker_driver.py ─▶ codex/app_server_client.py ─▶ Codex
          │        (async turn execution inside sandbox workspace)
          ├─▶ sandbox/manager.py (workspace dirs under EDS_WORK_DIR)
          ├─▶ control/repository.py (git checkout / candidate commit)
          └─▶ deployment/docker.py (docker build/run/health)
```

A CLI runner (`runner.py`) drives the same tools before the Supervisor and
A2A endpoint exist, and remains the developer entrypoint afterwards.

## 2. Key Decisions

- **D1 — Local-directory sandbox (pluggable).** v0.1 sandboxes are isolated
  directories under `EDS_WORK_DIR` (default `.eds/work/`), one per work
  order role. `sandbox/manager.py` exposes an interface so container-backed
  isolation can replace it without touching callers.
- **D2 — Asynchronous worker, polling tools.** `run_worker_task` starts a
  Codex turn in a background task and returns immediately;
  `get_worker_status` polls a persisted status (`starting/running/waiting/
  done/failed` + latest events). The Supervisor never blocks inside a single
  tool call. Worker questions/approvals surface as status `waiting` with the
  question payload; the Supervisor answers through the driver.
- **D3 — Codex client behind an interface.** `CodexAppServerClient` defines
  the control surface (start/resume thread, start turn, stream events,
  answer, approve). The v0.1.1 spike binds it to the real App Server
  (assumed `codex app-server` JSON-RPC; confirm in spike). A
  `ScriptedWorker` implementation of the same interface is the test double.
- **D4 — State: existing models, M1 subset.** Use the existing SQLAlchemy
  model; v0.1 writes only: identity, requirement, worker fields,
  candidate_commit, deployment fields, overall_status (+ events/evidence
  rows). Alembic initialized in v0.1.2; `init_schema()` remains the dev
  convenience.
- **D5 — Supervisor as ADK function-tool agent.** One `LlmAgent` whose tools
  are the Delivery Control subset; instruction loaded from
  `agent/prompts/supervisor_system.md`; model configured via env
  (`EDS_LLM_MODEL`, `EDS_LLM_API_KEY`, `GOOGLE_API_KEY` etc. per ADK).
  Session-per-work-order; every turn re-reads `get_current_state()`.
- **D6 — A2A thin adapter.** `a2a_api/server.py` maps Task send/get to
  work-order create/read; task state derives from `overall_status`
  (mapping in [a2a-interface design](../../designs/a2a-interface.md)).
- **D7 — Deployment via docker SDK.** `deployment/docker.py` builds the
  candidate image, runs it on an allocated port, polls `/` and `/docs`,
  persists URLs + health, returns the deployment record.
- **D8 — Config by environment.** `EDS_DATABASE_URL`,
  `EDS_CODEX_APP_SERVER_URL`, `EDS_TEMPLATE_REPO_URL`, `EDS_WORK_DIR`,
  `EDS_LLM_MODEL`, `EDS_A2A_URL` (for the external CLI client). No config
  files in v0.1.

## 3. M1 Tool Subset (implemented signatures)

```
get_work_order(id) → dict
update_work_order(id, **fields) → dict
get_current_state(id) → {phase, worker, deployment, gaps}
create_worker_runtime(work_order_id) → runtime_id      # sandbox + codex thread
get_worker_status(work_order_id) → {status, events, candidate_commit}
deploy_candidate(work_order_id, candidate_commit) → deployment record
get_deployment_status(deployment_id) → {status, base_url, docs_url, health}
record_evidence(work_order_id, kind, payload) → evidence_id
mark_complete(id, summary) / mark_failed(id, reason)
```

`create_inspector_runtime` / `get_inspector_status` stay stubs (v0.3).

## 4. Worker Task Contract

Input to the Worker turn: requirement text + acceptance criteria + workspace
path + test command + commit convention. Expected output events: file
changes, command executions, pytest result, final `done` with engineering
summary and candidate commit sha. The driver persists these as events and
evidence (`pytest_run`), and sets `candidate_commit` on the work order.

## 5. Testing Strategy

| Layer | What | Doubles |
|---|---|---|
| Unit | tools against a transactional PG (or SQLite-fallback) session; git/docker helpers | fake docker client |
| Contract | worker loop with `ScriptedWorker`; supervisor loop with scripted tools + fake LLM | ScriptedWorker, recorded states |
| Integration | real git + real docker build/run of template repo | none (docker required) |
| E2E (marked `e2e`) | full chain with real Codex + LLM + docker | none |

## 6. Non-Goals (v0.1)

No Inspector, no requirement-confirmation loop, no restart recovery beyond
durable rows, no PR delivery, no multi-project registry, no containerized
runtimes, no push notifications.
