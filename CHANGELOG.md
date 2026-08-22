# Changelog

All notable changes to the Engineering Delivery Service. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow the
milestone plan in `docs/milestones.md`.

## [Unreleased]

### Fixed

- Worker runtime crashes now surface in durable state instead of dying
  silently: an exception escaping a worker `execute` (e.g. an unspawnable
  `EDS_CODEX_APP_SERVER_URL` command) is caught by a crash guard around
  the worker thread and persisted as worker status `failed` plus a
  `worker.crash` audit event. Previously the thread died with the status
  stuck on `running` forever, and the Supervisor polled a dead worker
  with no way to detect it (observed live: a work order hung >10 min on
  `FileNotFoundError: http://localhost:1455`).
- Supervisor system prompt now distinguishes a worker **runtime crash**
  (restart the turn once via `start_worker_turn`; on recurrence
  `mark_failed` quoting the worker error) from an **engineering
  failure** (judge from evidence). Dogfooded end-to-end: crash →
  detect → one restart → same crash → `mark_failed` with the real
  error, all within one supervisor turn (~15 s).
- Turn-budget exhaustion now names the last observed turn error (e.g. a
  sustained LLM 429 quota outage) in the `mark_failed` reason, instead
  of the opaque "budget exhausted without a terminal decision" —
  observed live when every supervisor model call failed to
  `RESOURCE_EXHAUSTED` while the worker was still working.
- `.env.example`: `EDS_CODEX_APP_SERVER_URL` was shipped as
  `http://localhost:1455` — a value that looks like an endpoint but is
  executed as a command line. Now documents the command form and
  defaults to `codex app-server`.

### Chores

- Added in-app `.env` loading (`control/env.py`, python-dotenv): every
  entrypoint (`eds` CLI, `python -m a2a_api.server`,
  `python -m agent.runner`, `alembic`) bootstraps its environment from
  gitignored `.env` at the repository root, model credentials included —
  `GOOGLE_API_KEY` there is what enables the ADK Supervisor model, no
  shell exports needed. Exported variables keep precedence over the file.
- Extended `.env.example` with the model configuration block
  (`GOOGLE_API_KEY`, optional `GOOGLE_GENAI_USE_VERTEXAI`, `EDS_LLM_MODEL`).

### Docs

- README restructured for public release: design principles, architecture
  diagram (`docs/eds-arch.png`), and roadmap up front; setup, run
  instructions, configuration, and development workflow moved to the new
  `developer-guide.md`.

### v0.1 — Single Worker End-to-End (M1)

#### v0.1.5 — EDS CLI

- Added `cli.py` (console script `eds`, flat-layout packaging via
  hatchling): the reference external caller — `serve`, `submit`,
  `status --watch`, `open` over the A2A protocol only. Exit codes for
  scripting: 0 completed, 1 failed, 2 still running.
- Added `agent/deterministic.py`: rule-based fallback Supervisor model
  (`EDS_SUPERVISOR_BACKEND=deterministic`, `EDS_WORKER_SCRIPT`) so the
  full delivery loop runs in demos without LLM credentials; every
  stage decision derives from durable state.
- Declared `httpx` as an explicit dependency.

#### v0.1.4 — A2A endpoint

- Added `a2a_api/server.py`: EDS exposed as one Engineering Delivery
  Agent over the A2A JSON-RPC wire surface — `message/send` (requirement
  text in → work order created → supervisor launched in background →
  task `working`), `tasks/get` (task state derived from durable
  `overall_status`, never in-memory), `/.well-known/agent-card.json`,
  `/healthz`. Completed tasks carry artifacts: repository@commit,
  deployment URL, `/docs` URL, pytest evidence summary, delivery
  summary; failures carry the persisted reason.
- Added `agent.runner.start_supervised_delivery`: shared background
  launcher (CLI joins the thread; the endpoint returns immediately and
  callers poll durable state).
- Dependency: `a2a-sdk[http-server]` (server-side extras).
- Live dogfooding recorded as durable evidence (`human_acceptance_check`)
  against the real endpoint over real HTTP with a real Docker deployment.

#### v0.1.3 — ReAct Supervisor

- Added `agent/supervisor.py` (`build_supervisor`): ADK `LlmAgent` with
  the Delivery Control tool inventory plus deterministic engine-action
  tool wrappers that return structured errors instead of raising.
- Added `agent/runner.py` (`supervise`): run-loop with per-turn context
  re-rendered from durable state, one `supervisor_turn` audit event per
  turn, and a 25-turn budget that converts runaway loops into a
  persisted `mark_failed`. CLI: `python -m agent.runner`.

#### v0.1.2 — Durable state & tools

- Alembic migration 0001; Work Orders, audit events, evidence and
  deployment facts persisted in PostgreSQL.
- The nine M1 Delivery Control tools are real; worker registry is
  durable; the runner drives the flow through tools.

#### v0.1.1 — Worker engine

- CLI runner: requirement → sandbox → git checkout → worker turn
  (Codex or scripted) → pytest evidence → candidate commit → Docker
  deploy → live `/docs` URL.
