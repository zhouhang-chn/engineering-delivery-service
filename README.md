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

**Current entrypoint (v0.1.5 — `eds` CLI): the user test loop in four
commands.** Start the service, submit a requirement, watch EDS drive it
autonomously to a deployed FastAPI service, and open the delivered
Swagger UI. No A2A knowledge required.

```bash
# One-time durable state:
docker compose up -d postgres
uv run alembic upgrade head

# 1) start EDS (the A2A endpoint on uvicorn):
uv run eds serve

# 2) submit a requirement (in another shell):
uv run eds submit "Add a GET /hello endpoint returning {'hello': 'world'}"

# 3) watch it deliver (exit 0 completed, 1 failed, 2 still running):
uv run eds status wo-<id> --watch

# 4) open the delivered /docs in your browser ("Try it out" → Execute):
uv run eds open wo-<id>
```

`status` renders the task state plus artifacts — repository@commit,
deployment URL, `/docs` URL, pytest evidence, delivery summary — all
re-derived from durable PostgreSQL state on every poll. The endpoint
behind the CLI is the A2A surface from v0.1.4 (`message/send`,
`tasks/get`, agent card at `/.well-known/agent-card.json`); any
A2A-compatible client works too.

Prerequisites: a running Docker daemon (postgres + deployment); for the
default Supervisor an LLM credential (`EDS_LLM_MODEL`, default
`gemini-2.5-flash`, plus e.g. `GOOGLE_API_KEY`); the `codex` CLI logged
in (`codex login`) for real Worker turns.

**Demo mode (no LLM credential, no Codex):** a rule-based supervisor
backend and a scripted worker let the full loop run offline —

```bash
EDS_SUPERVISOR_BACKEND=deterministic \
EDS_WORKER_SCRIPT=examples/scripted_worker_hello.json \
uv run eds serve
```

Inspect any work order's durable snapshot from a fresh process:

```bash
uv run python -c "from tools.work_order import get_current_state; \
import sys, json; print(json.dumps(get_current_state(sys.argv[1]), indent=2))" \
  wo-<id>
```

One-shot alternatives: `uv run python -m agent.runner "<requirement>"`
(supervised, needs the LLM credential) and `uv run python runner.py
"<requirement>" --scripted examples/scripted_worker_hello.json`
(deterministic development runner).

| Variable | Default | Purpose |
|---|---|---|
| `EDS_DATABASE_URL` | `postgresql+psycopg://eds:eds@localhost:5432/eds` | durable Work Order state |
| `EDS_WORK_DIR` | `.eds/work` | sandboxes + published template repo |
| `EDS_TEMPLATE_REPO_URL` | auto-published `template/fastapi-service` | baseline repository to clone |
| `EDS_CODEX_APP_SERVER_URL` | `codex app-server` | Codex App Server command |
| `EDS_LLM_MODEL` | `gemini-2.5-flash` | Supervisor model (credentials via the ADK provider env, e.g. `GOOGLE_API_KEY`) |
| `EDS_A2A_HOST` / `EDS_A2A_PORT` | `127.0.0.1` / `8080` | A2A endpoint bind address (`eds serve`) |
| `EDS_A2A_URL` | `http://127.0.0.1:8080` | endpoint the `eds` CLI talks to |
| `EDS_SUPERVISOR_BACKEND` | `llm` | set `deterministic` for the credential-free demo backend |
| `EDS_WORKER_SCRIPT` | – | path to a scripted worker JSON (demo mode) |

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
recorded acceptance evidence; **v0.1.5 `eds` CLI** — the reference
external caller: serve / submit / status --watch / open, packaged as a
console script, plus a credential-free deterministic demo backend.
v0.1's iterations are complete.
