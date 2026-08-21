# v0.1.3 Design — ReAct Supervisor

Implements version design D5.

## Agent assembly

`agent/supervisor.py: build_supervisor()` returns an ADK `LlmAgent`:

- instruction: `agent/prompts/supervisor_system.md` + per-turn context
  header injected by the runner (work order id, current state summary)
- tools: the nine M1 tools registered as ADK function tools with typed,
  JSON-clean signatures (dicts in/out)
- model: from env (`EDS_LLM_MODEL`; credentials via the ADK provider env)

## Run loop

`agent/runner.py` (or `runner.py supervise <wo>`): per iteration — render
context from `get_current_state` → `Runner.run` one agent step → tools
execute → repeat until `mark_complete`/`mark_failed` or a turn budget
(default 25) is hit (then `mark_failed` with diagnostic reason). Every
loop iteration appends a `supervisor_turn` event (decision summary) for
diagnosability.

## Testing

- Contract: fake LLM scripted to call tools in a wrong-then-recovering
  order (e.g. deploy before candidate → observe failure → recover),
  asserting correct terminal state and bounded turns.
- Live (marked): real model + ScriptedWorker end-to-end; then one real
  Codex run.
