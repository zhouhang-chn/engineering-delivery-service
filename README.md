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

**Current entrypoint (v0.1.1 — worker engine): the CLI runner.**
Requirement in → sandbox → worker turn → pytest evidence → candidate
commit → docker deploy → live `/docs` URL out.

Prerequisites: a running Docker daemon; the `codex` CLI logged in
(`codex login`) only for real Worker turns.

```bash
# Scripted worker — no Codex account needed (demo path):
uv run python runner.py \
  "Add a GET /hello endpoint returning {'hello': 'world'}" \
  --scripted examples/scripted_worker_hello.json

# Real Codex worker:
uv run python runner.py \
  "Add a GET /time endpoint returning the current ISO timestamp"
```

The runner prints `docs url : http://localhost:<port>/docs` — open it in
a browser, "Try it out", and verify the delivered requirement. Useful
flags: `--port`, `--work-dir`, `--timeout` (`uv run python runner.py
--help` for all).

| Variable | Default | Purpose |
|---|---|---|
| `EDS_WORK_DIR` | `.eds/work` | sandboxes + published template repo |
| `EDS_TEMPLATE_REPO_URL` | auto-published `template/fastapi-service` | baseline repository to clone |
| `EDS_CODEX_APP_SERVER_URL` | `codex app-server` | Codex App Server command |

Default test runs skip suites that need external services; opt in with
`uv run pytest -m docker` and `uv run pytest -m codex`.

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
Codex worker. Next up: durable state (v0.1.2), ReAct Supervisor
(v0.1.3), A2A endpoint (v0.1.4), `eds` CLI (v0.1.5).
