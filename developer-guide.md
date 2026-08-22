# Developer Guide

How to run, configure, and develop EDS. For the system design, roadmap,
and documentation index see the [README](README.md).

## Setup

Requires Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
docker compose up -d postgres   # durable state
uv run pytest
uv run ruff check .
```

Configuration lives in `.env`: copy the template and fill in real
values — `cp .env.example .env`. The application loads the file itself
at every entrypoint (`eds` CLI, `python -m a2a_api.server`,
`python -m agent.runner`, `alembic`), model credentials included —
`GOOGLE_API_KEY` in `.env` is what enables the ADK Supervisor model —
so nothing needs to be exported in the shell. Exported environment
variables still win over the file when both are set. Real secrets go
only in gitignored `.env`; `.env.example` carries just the names.

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
re-derived from durable PostgreSQL state on every poll.

Prerequisites: a running Docker daemon (postgres + deployment); for the
default Supervisor an LLM credential (`EDS_LLM_MODEL`, default
`gemini-2.5-flash`, plus e.g. `GOOGLE_API_KEY`); the `codex` CLI logged
in (`codex login`) for real Worker turns.

## Demo mode (no LLM credential, no Codex)

A rule-based supervisor backend and a scripted worker let the full loop
run offline:

```bash
EDS_SUPERVISOR_BACKEND=deterministic \
EDS_WORKER_SCRIPT=examples/scripted_worker_hello.json \
uv run eds serve
```

## The A2A surface

The endpoint behind the CLI is the A2A JSON-RPC surface from v0.1.4:
`message/send`, `tasks/get`, agent card at
`/.well-known/agent-card.json`, health at `/healthz`. Any
A2A-compatible client works too — an A2A Task maps to one Engineering
Work Order (see
[docs/designs/a2a-interface.md](docs/designs/a2a-interface.md)).

## One-shot alternatives

`uv run python -m agent.runner "<requirement>"` runs one supervised
delivery in-process (needs the LLM credential);
`uv run python runner.py "<requirement>" --scripted
examples/scripted_worker_hello.json` is the deterministic development
runner.

## Inspecting durable state

Any work order's durable snapshot can be inspected from a fresh process:

```bash
uv run python -c "from tools.work_order import get_current_state; \
import sys, json; print(json.dumps(get_current_state(sys.argv[1]), indent=2))" \
  wo-<id>
```

## Configuration

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

## Tests

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

## Repository layout notes

Note: the A2A endpoint package is `a2a_api/`, not `a2a/` — a top-level
`a2a` package would shadow the `a2a-sdk` distribution at import time.
