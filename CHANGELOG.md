# Changelog

All notable changes to the Engineering Delivery Service. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow the
milestone plan in `docs/milestones.md`.

## [Unreleased]

### v0.1 — Single Worker End-to-End (M1, in progress)

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
