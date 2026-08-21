# v0.1.1 Design — Worker Engine

Implements version design D1–D3, D7–D8 for the engine path.

## Modules

- `sandbox/manager.py` — `create_sandbox(work_order_id, role)` returns
  `{sandbox_id, path}`; dirs under `EDS_WORK_DIR/<wo>/<role>/`;
  `destroy_sandbox` removes recursively (idempotent).
- `codex/app_server_client.py` — `CodexAppServerClient` (protocol bound in
  the spike; assumed `codex app-server` JSON-RPC over stdio):
  `start_thread`, `start_turn(thread_id, prompt) -> turn_id`,
  `poll_events(thread_id)`, `answer(thread_id, payload)`,
  `approve(thread_id, decision)`. Transport isolated in one private module.
- `codex/worker_driver.py` — `run_worker_task` spawns the turn in a
  background thread/process and persists status transitions
  (`starting→running→waiting?→done|failed`) + events to an in-memory
  job registry (v0.1.2 moves it to PostgreSQL); `get_worker_status` reads
  it. Also `ScriptedWorker` implementing the same interface from a JSON
  script of events.
- `control/repository.py` — `checkout` (clone + pinned baseline),
  `commit_candidate` (branch `eds/<wo>`, commit, return sha).
- `deployment/docker.py` — `deploy(image_tag|build_ctx, port)`,
  `health_check(base_url)` polling `/` and `/docs`; docker SDK client
  injected for tests.
- `runner.py` — CLI: `uv run python runner.py "requirement..."` executes:
  create work-order record (in-memory/SQLite now) → sandbox → checkout →
  worker turn (Codex or `--scripted`) → pytest evidence → commit candidate
  → docker deploy → print `/docs` URL.

## Contracts

Worker turn prompt template embeds: requirement, acceptance criteria,
workspace path, `uv run pytest` command, commit convention. The driver
extracts from completion events: candidate sha, test summary, remaining
concerns → persisted as evidence + summary.

## Testing

Unit: sandbox/git/docker helpers with fakes. Contract: full runner loop
against `ScriptedWorker` + fake docker (asserts deploy called with built
image and URLs returned). Integration (docker): real build/run/health of
the template repo. Live (marked): one real Codex turn.
