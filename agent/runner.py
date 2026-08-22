"""Supervise run-loop: the ReAct Supervisor drives one work order.

Per outer turn: re-render context from ``get_current_state`` (durable
state, never conversation memory) → run one ADK agent step-chain →
audit a ``supervisor_turn`` event with the tool calls and decision.
Repeat until ``mark_complete`` / ``mark_failed`` or the turn budget is
exhausted (then ``mark_failed`` with a diagnostic reason — a runaway
loop becomes a persisted failure, never an infinite run).

CLI: ``uv run python -m agent.runner "<requirement>"`` — same options
as runner.py, but the delivery order is decided by the Supervisor.

Usage:
  docker compose up -d postgres && uv run alembic upgrade head
  uv run python -m agent.runner "Add a GET /hello endpoint returning hello world"
  uv run python -m agent.runner "..." --scripted examples/scripted_worker_hello.json
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from agent.supervisor import (
    build_supervisor,
    configure_supervisor,
    current_config,
)
from control.state import append_event, session_scope
from runner import DEFAULT_WORKER_TIMEOUT_S, _log, _resolve_repo_url
from tools.work_order import TERMINAL_STATUSES, get_current_state, mark_failed, update_work_order

DEFAULT_TURN_BUDGET = 25
DECISION_EXCERPT_CHARS = 500
APP_NAME = "eds"
USER_ID = "eds-supervisor"


@dataclass
class SuperviseResult:
    """Outcome of one supervision: final durable state + turn accounting."""

    work_order_id: str
    overall_status: str
    terminal: bool = False
    turns: int = 0
    turn_budget: int = DEFAULT_TURN_BUDGET
    reason: str | None = None
    decision: str | None = None
    worker: dict = field(default_factory=dict)
    deployment: dict = field(default_factory=dict)


def render_turn_context(state: dict) -> str:
    """Render the per-turn context header from the durable snapshot."""
    worker = state["worker"]
    deployment = state["deployment"]
    recent = "\n".join(
        f"  - {event['type']} ({event['created_at']})" for event in state["recent_events"]
    )
    return (
        f"Work order {state['work_order_id']} — status: {state['overall_status']}\n"
        f"Requirement: {state['requirement']['confirmed_requirement']}\n"
        f"Acceptance criteria:\n"
        + "".join(f"  - {c}\n" for c in state["requirement"]["acceptance_criteria"])
        + "Worker:\n"
        f"  status={worker['status']} candidate_commit={worker['candidate_commit'] or '-'}\n"
        f"  summary={worker['summary'] or '-'} error={worker['error'] or '-'}\n"
        "Deployment:\n"
        f"  status={deployment['status']} health={deployment['health']} "
        f"docs_url={deployment['docs_url'] or '-'}\n"
        f"Open gaps: {state['gaps'] or '-'}\n"
        f"Evidence recorded so far: {state['evidence_count']}\n"
        f"Recent events:\n{recent}\n"
        "Continue driving this work order toward the goal using your tools."
    )


def supervise(
    work_order_id: str,
    *,
    agent=None,
    llm=None,
    turn_budget: int = DEFAULT_TURN_BUDGET,
    session_service=None,
) -> SuperviseResult:
    """Run the Supervisor on one work order until a terminal decision."""
    return asyncio.run(
        _supervise_async(
            work_order_id,
            agent=agent,
            llm=llm,
            turn_budget=turn_budget,
            session_service=session_service,
        )
    )


async def _supervise_async(
    work_order_id: str,
    *,
    agent=None,
    llm=None,
    turn_budget: int,
    session_service=None,
) -> SuperviseResult:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    active_agent = agent or build_supervisor(llm=llm)
    service = session_service or InMemorySessionService()
    # session-per-work-order; session state is a cache, PostgreSQL is the truth
    if await service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=work_order_id
    ) is None:
        await service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=work_order_id
        )
    runner = Runner(app_name=APP_NAME, agent=active_agent, session_service=service)

    turns = 0
    last_error: str | None = None
    for turn in range(1, turn_budget + 1):
        state = get_current_state(work_order_id)
        if state["overall_status"] in TERMINAL_STATUSES:
            break
        turns = turn
        message = types.Content(
            role="user",
            parts=[types.Part(text=render_turn_context(state))],
        )
        tool_calls: list[str] = []
        decision: str | None = None
        run_error: str | None = None
        try:
            async for event in runner.run_async(
                user_id=USER_ID, session_id=work_order_id, new_message=message
            ):
                for call in event.get_function_calls() or []:
                    tool_calls.append(call.name)
                if event.is_final_response() and event.content:
                    texts = [
                        part.text
                        for part in event.content.parts or []
                        if part.text
                    ]
                    if texts:
                        decision = texts[-1]
        except Exception as exc:  # noqa: BLE001 - a broken turn must not kill the loop
            run_error = f"{type(exc).__name__}: {exc}"

        payload = {"turn": turn, "tool_calls": tool_calls}
        if decision:
            payload["decision"] = decision[:DECISION_EXCERPT_CHARS]
        if run_error:
            payload["error"] = run_error[:DECISION_EXCERPT_CHARS]
            last_error = run_error
        with session_scope() as session:
            append_event(session, work_order_id, "supervisor_turn", payload)

    final_state = get_current_state(work_order_id)
    if final_state["overall_status"] not in TERMINAL_STATUSES:
        reason = (
            f"supervisor turn budget ({turn_budget}) exhausted without a terminal decision"
        )
        if last_error:
            # the budget message alone hides the cause (e.g. every model
            # call dying to a 429 quota) — name the last observed error
            reason = f"{reason}; last turn error: {last_error[:DECISION_EXCERPT_CHARS]}"
        mark_failed(work_order_id, reason)
        final_state = get_current_state(work_order_id)

    return _result_from_state(work_order_id, final_state, turns, turn_budget)


def _result_from_state(
    work_order_id: str,
    state: dict,
    turns: int,
    turn_budget: int,
) -> SuperviseResult:
    """Build the result from the durable final state (never from memory)."""
    terminal = state["overall_status"] in TERMINAL_STATUSES
    reason = None
    for artifact in reversed(state["artifacts"] or []):
        if artifact.get("type") == "completion_summary":
            reason = artifact.get("summary")
            break
        if artifact.get("type") == "failure_reason":
            reason = artifact.get("reason")
            break
    return SuperviseResult(
        work_order_id=work_order_id,
        overall_status=state["overall_status"],
        terminal=terminal,
        turns=turns,
        turn_budget=turn_budget,
        reason=reason,
        worker=dict(state["worker"]),
        deployment=dict(state["deployment"]),
    )


def start_supervised_delivery(
    requirement: str,
    *,
    repo_url: str | None = None,
    base_dir: str | Path | None = None,
    port: int | None = None,
    worker=None,
    docker_client=None,
    test_command: str | None = None,
    turn_budget: int = DEFAULT_TURN_BUDGET,
) -> tuple[str, threading.Thread]:
    """Create the work order and launch ``supervise`` in a background thread.

    Shared by the CLI (joins the thread) and the A2A endpoint (returns
    immediately; callers poll durable state). Progress is observable
    through ``get_current_state`` from the moment this returns.
    """
    from codex.worker_driver import CodexWorkerDriver, ScriptedWorker
    from sandbox import manager as sandbox_manager

    config = current_config()
    resolved = {
        "worker": worker if worker is not None else config.worker,
        "docker_client": docker_client if docker_client is not None else config.docker_client,
        "base_dir": Path(base_dir).resolve()
        if base_dir is not None
        else (Path(config.base_dir).resolve() if config.base_dir else sandbox_manager.work_dir()),
        "port": port if port is not None else config.port,
        "test_command": test_command if test_command is not None else config.test_command,
        "repo_url": repo_url if repo_url is not None else config.repo_url,
        "llm_factory": config.llm_factory,
    }
    if resolved["worker"] is None:
        # demo/tests: a scripted worker replaying a canned Codex turn
        worker_script = os.environ.get("EDS_WORKER_SCRIPT")
        resolved["worker"] = (
            ScriptedWorker(worker_script) if worker_script else CodexWorkerDriver()
        )
    if resolved["llm_factory"] is None and os.environ.get("EDS_SUPERVISOR_BACKEND") == "deterministic":
        # demo/tests: rule-based supervisor (no LLM credentials needed)
        from agent.deterministic import deterministic_llm_factory

        resolved["llm_factory"] = deterministic_llm_factory
    resolved_base = resolved["base_dir"]
    resolved_base.mkdir(parents=True, exist_ok=True)
    work_order_id = f"wo-{uuid.uuid4().hex[:12]}"
    update_work_order(
        work_order_id,
        original_request=requirement,
        confirmed_requirement=requirement,
        repository=resolved["repo_url"] or _resolve_repo_url(resolved_base),
        overall_status="in_progress",
    )
    configure_supervisor(**resolved)
    agent = (
        build_supervisor(llm=resolved["llm_factory"](work_order_id))
        if resolved["llm_factory"]
        else None
    )
    thread = threading.Thread(
        target=supervise,
        args=(work_order_id,),
        kwargs={"agent": agent, "turn_budget": turn_budget},
        daemon=True,
        name=f"eds-supervisor-{work_order_id}",
    )
    thread.start()
    return work_order_id, thread


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: create the work order, let the Supervisor deliver it."""
    parser = argparse.ArgumentParser(
        prog="agent.runner",
        description="Requirement in, Supervisor-delivered /docs out.",
    )
    parser.add_argument("requirement", help="the engineering requirement to deliver")
    parser.add_argument(
        "--scripted",
        metavar="SCRIPT_JSON",
        help="drive the worker from a JSON script instead of real Codex",
    )
    parser.add_argument("--port", type=int, default=None, help="host port for the deployment")
    parser.add_argument("--repo-url", default=None, help="template repository to clone")
    parser.add_argument("--work-dir", default=None, help="sandbox root directory")
    parser.add_argument("--turn-budget", type=int, default=DEFAULT_TURN_BUDGET)
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_WORKER_TIMEOUT_S, help="worker timeout seconds"
    )
    args = parser.parse_args(argv)

    from codex.worker_driver import ScriptedWorker
    from control.env import load_env
    from sandbox import manager as sandbox_manager

    load_env()

    base_dir = (
        Path(args.work_dir).resolve()
        if args.work_dir is not None
        else sandbox_manager.work_dir()
    )
    work_order_id, thread = start_supervised_delivery(
        args.requirement,
        repo_url=args.repo_url,
        base_dir=base_dir,
        port=args.port,
        worker=ScriptedWorker(args.scripted) if args.scripted else None,
    )
    _log(f"work order {work_order_id}: supervising '{args.requirement}'")
    thread.join()
    state = get_current_state(work_order_id)
    result = _result_from_state(work_order_id, state, turns=0, turn_budget=args.turn_budget)

    print()
    print(f"work order   : {result.work_order_id}")
    print(f"events       : {state['event_count']} (supervisor turns audited)")
    print(f"worker       : {result.worker.get('status')}"
          + (f" ({result.worker.get('error')})" if result.worker.get("error") else ""))
    print(f"candidate    : {result.worker.get('candidate_commit') or '-'}")
    print(f"deployment   : {result.deployment.get('status') or '-'} "
          f"({result.deployment.get('health') or '-'})")
    print(f"docs url     : {result.deployment.get('docs_url') or '-'}")
    print(f"final        : {result.overall_status}"
          + (f" — {result.reason}" if result.reason else ""))
    return 0 if result.overall_status == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
