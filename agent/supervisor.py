"""ReAct Supervisor (Google ADK): agent assembly and function tools.

The free-running top-level controller. It observes Work Order state,
reasons about the next action, and calls Delivery Control / Worker
tools until all acceptance criteria are verified and the deployment is
live at ``/docs``. It never edits code or runs tests itself — engine
actions (worker turn, acceptance tests, deploy) are exposed as
deterministic tools whose results the agent reasons over.

See docs/designs/supervisor.md and architecture doc section 7.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from codex.worker_driver import (
    DEFAULT_TEST_COMMAND,
    WorkerTask,
    run_worker_task,
)
from control import repository
from tools.deployment import deploy_candidate as _deploy_candidate
from tools.deployment import get_deployment_status
from tools.evidence import record_evidence
from tools.runtime import create_worker_runtime as _create_worker_runtime
from tools.work_order import (
    get_current_state,
    get_work_order,
    mark_complete,
    mark_failed,
)
from tools.work_order import update_work_order as _update_work_order
from tools.worker import get_worker_status

PROMPT_PATH = Path(__file__).parent / "prompts" / "supervisor_system.md"
DEFAULT_MODEL = "gemini-2.5-flash"


@dataclass
class SupervisorToolConfig:
    """Runtime dependencies injected into the engine-action tools.

    Mirrors ``control.state.configure``: tests and the CLI point the
    wrappers at their own worker / docker client / sandbox root; the
    defaults hit the real Codex driver and real Docker.
    """

    worker: object = None
    docker_client: object = None
    base_dir: str | Path | None = None
    port: int | None = None
    test_command: str | None = None


_config = SupervisorToolConfig()


def configure_supervisor(**kwargs) -> None:
    """Install the runtime dependencies the tool wrappers use."""
    global _config
    _config = SupervisorToolConfig(**kwargs)


def reset_supervisor_config() -> None:
    """Return to default dependencies (real Codex driver, real Docker)."""
    global _config
    _config = SupervisorToolConfig()


def _error(exc: Exception) -> dict:
    """Render a tool failure as a JSON-safe error result for the agent."""
    return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# --------------------------------------------------------------------------
# Work Order observation and lifecycle (thin re-exports of v0.1.2 tools;
# signatures are already typed and JSON-clean).
# --------------------------------------------------------------------------


def create_worker_runtime(work_order_id: str) -> dict:
    """Provision the Worker sandbox for this work order (idempotent)."""
    try:
        return _create_worker_runtime(work_order_id, base_dir=_config.base_dir)
    except Exception as exc:  # noqa: BLE001 - failures must reach the agent
        return _error(exc)


def update_work_order(
    work_order_id: str, gaps: list[str] | None = None
) -> dict:
    """Record supervisor-maintained facts (open gaps) on the work order."""
    fields: dict = {}
    if gaps is not None:
        fields["gaps"] = list(gaps)
    if not fields:
        return {"ok": False, "error": "nothing to update: pass gaps"}
    try:
        return _update_work_order(work_order_id, **fields)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


# --------------------------------------------------------------------------
# Engine actions: git checkout, worker turn, acceptance tests, candidate
# commit, deploy. Deterministic executors — the agent decides when.
# --------------------------------------------------------------------------


def checkout_baseline(work_order_id: str) -> dict:
    """Clone the project repository into the worker sandbox (idempotent).

    Returns the baseline commit sha; re-issuing after a successful
    checkout returns the recorded baseline without touching git again.
    """
    from tools.project import resolve_project

    try:
        work_order = get_work_order(work_order_id)
        if work_order.get("baseline_commit"):
            resolve = resolve_project(work_order_id)
            return {
                "ok": True,
                "baseline_commit": work_order["baseline_commit"],
                "repository": resolve["repository"],
                "already_checked_out": True,
            }
        resolve = resolve_project(work_order_id)
        repo_dir = repository.worker_repo_dir(work_order_id, base_dir=_config.base_dir)
        baseline = repository.checkout(
            work_order_id, resolve["repository"], None, repo_dir=repo_dir
        )
        _update_work_order(work_order_id, baseline_commit=baseline)
        return {
            "ok": True,
            "baseline_commit": baseline,
            "repository": resolve["repository"],
            "already_checked_out": False,
        }
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


def start_worker_turn(work_order_id: str) -> dict:
    """Start one Worker turn (Codex or scripted) in the sandbox workspace.

    Non-blocking: returns immediately with the initial status; poll
    ``get_worker_status`` until ``done`` or ``failed``.
    """
    from control.state import append_event, session_scope

    try:
        work_order = get_work_order(work_order_id)
        requirement = work_order.get("confirmed_requirement") or work_order.get(
            "original_request"
        )
        if not requirement:
            return {"ok": False, "error": "work order has no requirement to hand the worker"}
        repo_dir = repository.worker_repo_dir(work_order_id, base_dir=_config.base_dir)
        if not repo_dir.exists():
            return {
                "ok": False,
                "error": f"worker workspace missing: {repo_dir} (checkout_baseline first)",
            }
        task = WorkerTask(
            requirement=requirement,
            workspace=repo_dir,
            acceptance_criteria=tuple(work_order.get("acceptance_criteria") or ()),
            test_command=_config.test_command or DEFAULT_TEST_COMMAND,
        )
        run_worker_task(work_order_id, task, worker=_config.worker)
        with session_scope() as session:
            append_event(
                session,
                work_order_id,
                "worker.turn_started",
                {"test_command": task.test_command},
            )
        status = get_worker_status(work_order_id)
        return {"ok": True, "status": status["status"], "summary": status["summary"]}
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


def run_acceptance_tests(work_order_id: str) -> dict:
    """Run the test suite in the worker workspace and record the evidence.

    Independent of the Worker: EDS executes the suite itself and
    persists the result. Returns the evidence payload — the agent
    decides what to do with a failing suite.
    """
    try:
        from runner import run_pytest_evidence

        repo_dir = repository.worker_repo_dir(work_order_id, base_dir=_config.base_dir)
        if not repo_dir.exists():
            return {"ok": False, "error": f"workspace missing: {repo_dir}"}
        evidence = run_pytest_evidence(
            repo_dir, _config.test_command or DEFAULT_TEST_COMMAND
        )
        record_evidence(work_order_id, "pytest_run", evidence)
        return {"ok": True, "evidence": evidence}
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


def commit_candidate(work_order_id: str, message: str | None = None) -> dict:
    """Commit the Worker's changes on the candidate branch; persist the sha."""
    try:
        work_order = get_work_order(work_order_id)
        requirement = work_order.get("confirmed_requirement") or "work order"
        repo_dir = repository.worker_repo_dir(work_order_id, base_dir=_config.base_dir)
        commit = repository.commit_candidate(
            work_order_id, message or f"feat: {requirement[:72]}", repo_dir=repo_dir
        )
        _update_work_order(work_order_id, candidate_commit=commit)
        return {"ok": True, "candidate_commit": commit}
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


def deploy_candidate(
    work_order_id: str, candidate_commit: str | None = None
) -> dict:
    """Build and run the candidate; persist deployment facts + evidence.

    ``candidate_commit`` defaults to the work order's recorded
    candidate; an explicit sha must match it (deploying anything else
    is an error, not a shortcut).
    """
    try:
        work_order = get_work_order(work_order_id)
        recorded = work_order.get("candidate_commit")
        if candidate_commit is None:
            candidate_commit = recorded
        if not candidate_commit or candidate_commit != recorded:
            recorded_desc = recorded[:12] if recorded else "none"
            return {
                "ok": False,
                "error": (
                    f"candidate_commit {candidate_commit[:12] if candidate_commit else 'none'} "
                    f"is not the recorded candidate ({recorded_desc}); "
                    "commit_candidate first"
                ),
            }
        record = _deploy_candidate(
            work_order_id,
            candidate_commit,
            port=_config.port,
            client=_config.docker_client,
            base_dir=_config.base_dir,
        )
        if record["health"] == "healthy":
            record_evidence(
                work_order_id,
                "deployment_check",
                {
                    "base_url": record["base_url"],
                    "docs_url": record["docs_url"],
                    "health": "healthy",
                },
            )
        record["ok"] = True
        return record
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


TOOL_FUNCTIONS = [
    get_work_order,
    update_work_order,
    get_current_state,
    create_worker_runtime,
    checkout_baseline,
    start_worker_turn,
    get_worker_status,
    run_acceptance_tests,
    commit_candidate,
    deploy_candidate,
    get_deployment_status,
    record_evidence,
    mark_complete,
    mark_failed,
]


def load_supervisor_instruction() -> str:
    """Read the system prompt from agent/prompts/supervisor_system.md."""
    return PROMPT_PATH.read_text()


def build_supervisor(*, llm=None, model: str | None = None):
    """Assemble the ADK LlmAgent wired with the Delivery Control tools.

    Model resolution: explicit ``llm`` (tests) > ``model`` argument >
    ``EDS_LLM_MODEL`` env > :data:`DEFAULT_MODEL`. Credentials come from
    the ADK provider environment (e.g. ``GOOGLE_API_KEY``).
    """
    from google.adk.agents import LlmAgent

    return LlmAgent(
        name="eds_supervisor",
        model=llm or model or os.environ.get("EDS_LLM_MODEL") or DEFAULT_MODEL,
        instruction=load_supervisor_instruction(),
        description=(
            "Autonomous engineering delivery supervisor: drives a work "
            "order from requirement to a deployed, verified service."
        ),
        tools=TOOL_FUNCTIONS,
    )
