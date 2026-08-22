# Engineering Delivery Service (EDS)

An autonomous engineering delivery service. It receives an **Engineering
Work Order** via A2A (not a coding prompt) and drives it autonomously:

```
Requirement → Development → Testing → Inspection → Deployment → Acceptance
```

MVP scope: **FastAPI API development and deployment** — deliver a running
service whose `/docs` (Swagger UI) a human can open, "Try it out", and
verify.

## Architecture in one paragraph

The top-level controller is a free-running **ReAct Supervisor** (Google
ADK). Deterministic **Delivery Control Tools** provide reliable actions
over durable **PostgreSQL** Work Order state. **Worker** and **Inspector**
are full Codex App Server runtimes in separate sandboxes: the Worker
produces a candidate commit; the Inspector independently verifies it
against acceptance criteria and returns ACCEPT / REJECT. The Supervisor
owns the loop. There is deliberately no deterministic workflow layer.

```
agent/        ReAct Supervisor + prompts
a2a_api/      A2A endpoint (Task ≈ Engineering Work Order)
tools/        Delivery Control tools exposed to the Supervisor
control/      Deterministic state / git / policy primitives
codex/        Codex App Server client + worker/inspector drivers
sandbox/      Sandbox lifecycle (writable worker, clean inspector)
deployment/   Docker deployment runtime
db/           SQLAlchemy models + alembic migrations
docs/         designs/ (design doc set), milestones.md, refer/ (source draft)
```

Note: the A2A endpoint package is `a2a_api/`, not `a2a/` — a top-level
`a2a` package would shadow the `a2a-sdk` distribution at import time.

## Milestones

1. Single Worker end-to-end (A2A → Codex → pytest → Docker → /docs)
2. Durable delivery control (PostgreSQL state + control tools)
3. Independent Inspector (worker→inspector→feedback loop)
4. Requirement confirmation + HITL clarification
5. Project-aware delivery (registry, repos, worktrees, PRs)
6. Recoverable autonomous delivery (crash/retry/resume)

## Setup

Requires Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
docker compose up -d postgres   # durable state
uv run pytest
uv run ruff check .
```

## Running EDS

The runnable surface grows iteration by iteration; this section is
rewritten at the end of every iteration to describe the current
entrypoint.

**Current entrypoint (v0.1.4 — A2A endpoint): `uv run python -m
a2a_api.server`.** EDS is one Engineering Delivery Agent: an A2A task
(`message/send`) carrying a requirement becomes a work order, an ADK
`LlmAgent` Supervisor drives it autonomously (runtime → checkout →
worker turn → acceptance tests → candidate commit → deploy), and the
caller polls `tasks/get` until `completed` — with artifacts
(repository@commit, deployment URL, `/docs` URL, pytest evidence,
delivery summary) or `failed` with the persisted reason. Task state
derives from durable PostgreSQL state, never memory.

Prerequisites: a running Docker daemon (postgres + deployment); an LLM
credential for the Supervisor (`EDS_LLM_MODEL`, default
`gemini-2.5-flash`, plus e.g. `GOOGLE_API_KEY`); the `codex` CLI
logged in (`codex login`) only for real Worker turns.

```bash
# One-time durable state:
docker compose up -d postgres
uv run alembic upgrade head

# Serve the A2A endpoint (default 127.0.0.1:8080; EDS_A2A_PORT to change):
uv run python -m a2a_api.server
```

Talk to it with any A2A-compatible client — raw JSON-RPC over HTTP:

```bash
# Submit a delivery task:
curl -s http://127.0.0.1:8080/ -H 'Content-Type: application/json' -d '{
  "jsonrpc": "2.0", "id": 1, "method": "message/send",
  "params": {"message": {"messageId": "m1", "role": "user",
    "parts": [{"kind": "text",
      "text": "Add a GET /hello endpoint returning {\"hello\": \"world\"}"}]}}}'

# Poll it (use the task id from the response):
curl -s http://127.0.0.1:8080/ -H 'Content-Type: application/json' -d '{
  "jsonrpc": "2.0", "id": 2, "method": "tasks/get",
  "params": {"id": "wo-<id>"}}'
```

A `completed` task's artifacts include the `docs_url` — open it in a
browser, "Try it out", and verify the delivered requirement. The agent
card is at `/.well-known/agent-card.json`; the endpoint also serves its
own `/docs`. Inspect any work order's durable snapshot from a fresh
process:

```bash
uv run python -c "from tools.work_order import get_current_state; \
import sys, json; print(json.dumps(get_current_state(sys.argv[1]), indent=2))" \
  wo-<id>
```

Without a long-running server, the same supervised delivery runs
one-shot from the CLI (`python -m agent.runner "<requirement>"
--scripted examples/scripted_worker_hello.json` — needs the same LLM
credential), and the deterministic no-LLM runner remains for
development:

```bash
uv run python runner.py "Add a GET /hello endpoint returning hello world" \
  --scripted examples/scripted_worker_hello.json
```

Useful launcher flags: `--port`, `--work-dir`, `--turn-budget`,
`--timeout` (`uv run python -m agent.runner --help` for all).

| Variable | Default | Purpose |
|---|---|---|
| `EDS_DATABASE_URL` | `postgresql+psycopg://eds:eds@localhost:5432/eds` | durable Work Order state |
| `EDS_WORK_DIR` | `.eds/work` | sandboxes + published template repo |
| `EDS_TEMPLATE_REPO_URL` | auto-published `template/fastapi-service` | baseline repository to clone |
| `EDS_CODEX_APP_SERVER_URL` | `codex app-server` | Codex App Server command |
| `EDS_LLM_MODEL` | `gemini-2.5-flash` | Supervisor model (credentials via the ADK provider env, e.g. `GOOGLE_API_KEY`) |
| `EDS_A2A_HOST` / `EDS_A2A_PORT` | `127.0.0.1` / `8080` | A2A endpoint bind address |

Default test runs skip suites that need external services; opt in with
`uv run pytest -m docker`, `uv run pytest -m codex` and
`uv run pytest -m llm`.

## Development workflow

Development follows the version-driven workflow in
[.agents/skills/development-workflow/SKILL.md](.agents/skills/development-workflow/SKILL.md):
each version (`vX.Y-description`, mapped to the milestone plan in
[docs/milestones.md](docs/milestones.md)) ships its own
`docs/versions/vX.Y-*/` docs (gap analysis, design, action plan,
implementation notes, retrospect) and is closed out with the
version-retrospect skill and the automated gate:

```bash
uv run python .agents/scripts/verify_version.py <version-dir>
```

Commit messages follow the `<type>(<scope>): <summary>` standard. Install
the enforcing git hooks once per clone:

```bash
git config core.hooksPath .agents/scripts/githooks
```

## Status

v0.1 (single worker end-to-end) in progress. Delivered: **v0.1.1 worker
engine** — the CLI runner turns a requirement into a deployed FastAPI
service with pytest evidence and a live `/docs`, via a scripted or real
Codex worker; **v0.1.2 durable state & tools** — work orders, audit
events, evidence and deployment facts live in PostgreSQL (alembic
migration 0001), the M1 Delivery Control tools are real, the worker
registry is durable, and the runner drives the flow through tools;
**v0.1.3 ReAct Supervisor** — an ADK `LlmAgent` decides the delivery
order autonomously over the same tools, bounded by a turn budget, every
turn audited; **v0.1.4 A2A endpoint** — EDS is callable as one
Engineering Delivery Agent over the A2A JSON-RPC surface (`message/send`
→ `tasks/get` → `completed` with artifacts), dogfooded end to end with
recorded acceptance evidence. Next up: `eds` CLI (v0.1.5).
