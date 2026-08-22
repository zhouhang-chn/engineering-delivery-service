# v0.1.1 Implementation Notes — Worker Engine

## Key Decisions

- 2026-08-22 (planning): worker status registry starts in-memory; PostgreSQL
  migration is explicitly v0.1.2 scope, so the interface must not leak the
  storage choice.
- T2 spike: `CodexAppServerClient` binds to `codex app-server`
  (codex-cli 0.146.0) over **newline-delimited JSON-RPC 2.0 on stdio**.
  Confirmed surface: `initialize(clientInfo)` → `thread/start {cwd,
  approvalPolicy, config}` → `turn/start {threadId, input:[{type:"text"}]}`;
  events arrive as notifications (`thread/status/changed`, `turn/started`,
  `item/started`, `item/completed`, `error`, `turn/completed`); approvals are
  server→client requests (`item/commandExecution/requestApproval`, …) answered
  with `{"decision": "accept"|"reject"}`. `turn.status` terminal values:
  `completed | interrupted | failed`. The design's assumed interface mapped
  1:1; `poll_events` is implemented as a drain of the client-side notification
  buffer (the wire is push, not poll).
- Worker turns run with `approvalPolicy: "never"` + sandbox
  `workspace-write` (network on) so the Worker is fully autonomous; the reply
  policy hook (`set_reply_policy`) remains for v0.4 HITL.
- The in-repo template (`template/fastapi-service`, no `.git`) is published
  once into a local bare repo (`<work-dir>/template.git`) via
  `ensure_bare_repo`, which then serves as the default
  `EDS_TEMPLATE_REPO_URL`. This keeps the single-repository discipline while
  giving checkout a real clone target; an env override accepts any remote.
- Test fixtures clone the real template directory, so contract/integration
  tests exercise the exact baseline the runner publishes.
- `EDS_CODEX_APP_SERVER_URL` carries the app-server *command* (default
  `codex app-server`) rather than an HTTP URL — the only transport codex-cli
  exposes today; the config name is kept per design D8 for a future HTTP
  endpoint.
- Contract-test fake docker (`tests/helpers/fake_docker.py`) runs a real
  local HTTP server per "container", so the deployment health check
  exercises its genuine HTTP probing path without a docker daemon.

## Deviations from Design

- **Live Codex delivery blocked by account quota.** The ChatGPT Codex
  account hit its usage limit during the spike ("try again at Aug 27th,
  2026 2:32 PM"). Evidence: the runner's live attempt
  (`uv run python runner.py "Add a GET /time endpoint …"`) drove a real
  thread+turn and failed exactly as designed — `error` notification →
  `turn/completed{status: failed}` → worker `failed` → no deploy, exit 1.
  The marked `codex` test skips with the quota message. Full-chain demo
  criterion was instead demonstrated via `--scripted` with **real docker**:
  `docs url: http://localhost:58943/docs` serving `{"hello":"world"}` on
  `/hello` (evidence in this iteration's action plan). Re-run the live
  delivery after Aug 27 or with a quota-carrying account.
- Iteration production LOC ≈ 1,300 (estimate was ~700): the JSON-RPC client
  (~260) and its threading/pumping took more lines than a thin HTTP wrapper
  would have. Still within the 1,000–3,000 version budget.

## Bugs Encountered

- `git push` to the published template repo failed (exit 128) when
  `EDS_WORK_DIR` was a relative path: git resolves push URLs against the
  process cwd, not `-C`. Fix: `sandbox.manager.work_dir()` now always
  returns resolved absolute paths.
- pytest evidence parsed "0 passed" for real runs: the summary line was
  taken from the last line of stdout+stderr combined, but stderr warnings
  follow it. Fix: parse the last matching summary line from stdout.
- `ensure_bare_repo` staging copy initially included the source's `.git`
  (making the commit a no-op → "nothing to commit"); fixed with
  `ignore=shutil.ignore_patterns(".git")`.
- Docker integration tests leaked containers: `import docker.errors` inside
  a `finally` shadowed the module-level `from deployment import docker`,
  so cleanup raised `AttributeError`. Fixed by importing `docker.errors`
  at module top and aliasing the deployment module.

## Lessons Learned

- Spike-first paid off: one 3-minute live probe against `codex app-server`
  (plus its `generate-json-schema` bundle) pinned the framing, method names
  and event shapes before any client code was written; the client worked
  against the real server on first try.
- Quota/auth limits of external agent runtimes must be a first-class failure
  mode: the runner now degrades cleanly (worker failed → no deploy → exit 1)
  and the marked test skips with the account message instead of hanging.
- Absolute paths at the storage boundary (work-dir resolution) prevent a
  whole class of subprocess-cwd bugs across git/docker/codex.
