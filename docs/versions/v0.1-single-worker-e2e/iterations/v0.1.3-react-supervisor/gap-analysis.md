# v0.1.3 Gap Analysis — ReAct Supervisor

**Goal:** replace the runner's hardcoded step order with an ADK ReAct
Supervisor that autonomously drives a work order to deployment using the
v0.1.2 tools.

**Current state:** `agent/supervisor.py` is a stub; the prompt draft exists;
no ADK wiring; the runner encodes the flow deterministically.

**Gaps:** ADK agent assembly (tools registration, instruction from
`agent/prompts/`) · model/env configuration · supervisor run-loop entrypoint
(ADK Runner, session per work order) · contract tests with a fake LLM ·
prompt tuning from observed behavior.

**Risks:** ADK API churn (pin version, thin wrapper); flaky loops from weak
prompts (bound turns, log every decision as events for diagnosis).
