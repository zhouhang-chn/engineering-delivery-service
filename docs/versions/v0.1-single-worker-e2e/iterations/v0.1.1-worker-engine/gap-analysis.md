# v0.1.1 Gap Analysis — Worker Engine

**Goal:** the engineering engine without any agent layer: given a requirement
string, produce a deployed FastAPI service with passing tests and a live
`/docs` — driven by a CLI runner.

**Current state:** all engine modules are `NotImplementedError` stubs; no
template repository exists; no Codex binding has been validated.

**Gaps:** template repo · Codex App Server binding (spike) · sandbox
workspaces · git checkout/commit · worker driver (async turn + status) ·
pytest evidence capture · docker build/run/health · CLI runner ·
ScriptedWorker double.

**Key risks:** Codex API mismatch (spike first); docker permissions
(preflight). See version gap-analysis §4.
