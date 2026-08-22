"""CLI runner: requirement in, deployed <port>/docs out.

Drives the delivery engine end to end:

  work order -> sandbox -> git checkout -> Worker turn (Codex or scripted)
  -> pytest evidence -> candidate commit -> docker deploy -> health check

Since v0.1.2 every step goes through the Delivery Control tools: the
work order, its audit events, evidence and deployment facts live in
PostgreSQL and survive restarts (`get_current_state`). The Supervisor
(v0.1.3) and A2A endpoint (v0.1.4) will call the same tools; this
runner remains the developer entrypoint.

Usage:
  docker compose up -d postgres && uv run alembic upgrade head
  uv run python runner.py "Add a GET /hello endpoint returning hello world"
  uv run python runner.py "..." --scripted examples/scripted_worker_hello.json
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from codex.worker_driver import (
    CodexWorkerDriver,
    ScriptedWorker,
    WorkerTask,
    run_worker_task,
)
from control import repository
from control import state as control_state
from sandbox import manager as sandbox_manager
from tools.deployment import deploy_candidate
from tools.evidence import record_evidence
from tools.project import resolve_project
from tools.runtime import create_worker_runtime
from tools.work_order import (
    get_current_state,
    mark_complete,
    mark_failed,
    update_work_order,
)
from tools.worker import get_worker_status

PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATE_SOURCE = PROJECT_ROOT / "template" / "fastapi-service"
DEFAULT_WORKER_TIMEOUT_S = 3600.0
POLL_INTERVAL_S = 1.0


@dataclass
class DeliveryResult:
    """Everything the delivery loop produced for one work order."""

    work_order_id: str
    requirement: str
    repo_url: str
    baseline_commit: str | None = None
    worker_status: str = "starting"
    worker_summary: str | None = None
    worker_error: str | None = None
    pytest_evidence: dict | None = None
    candidate_commit: str | None = None
    deployment_status: str | None = None
    deployment_health: str | None = None
    base_url: str | None = None
    docs_url: str | None = None
    port: int | None = None
    overall_status: str = "in_progress"
    evidence: list[dict] = field(default_factory=list)


def new_work_order_id() -> str:
    """Generate a work order id (short, filesystem-safe)."""
    return f"wo-{uuid.uuid4().hex[:12]}"


def _log(message: str) -> None:
    print(f"[eds] {message}", flush=True)


def run_pytest_evidence(repo_dir: Path, test_command: str) -> dict:
    """Run the test suite in the workspace and capture verifiable evidence."""
    proc = subprocess.run(
        test_command,
        shell=True,
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    output = (proc.stdout + proc.stderr).strip()
    return {
        "status": "passed" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        **_parse_pytest_summary(proc.stdout),
        "output_tail": output[-2000:],
    }


def _parse_pytest_summary(stdout: str) -> dict:
    """Extract passed/failed/error counts from the pytest summary line.

    Scans backwards: stderr noise (warnings) can follow the summary when
    streams are interleaved, so the last line is not always the summary.
    """
    passed = failed = errors = 0
    summary_line = ""
    for line in reversed(stdout.strip().splitlines()):
        counts = re.findall(r"(\d+) (passed|failed|error)", line)
        if counts or "no tests ran" in line:
            summary_line = line.strip()
            for number, word in counts:
                if word == "passed":
                    passed = int(number)
                elif word == "failed":
                    failed = int(number)
                else:
                    errors = int(number)
            break
    return {"passed": passed, "failed": failed, "errors": errors, "summary_line": summary_line}


def _resolve_repo_url(work_dir: Path) -> str:
    """Use EDS_TEMPLATE_REPO_URL when set; otherwise publish the in-repo template."""
    import os

    env_url = os.environ.get("EDS_TEMPLATE_REPO_URL")
    if env_url:
        return env_url
    bare = work_dir / "template.git"
    repository.ensure_bare_repo(TEMPLATE_SOURCE, bare)
    return str(bare)


def run_delivery(
    requirement: str,
    *,
    acceptance_criteria: tuple[str, ...] | list[str] = (),
    worker=None,
    docker_client=None,
    repo_url: str | None = None,
    work_dir: str | Path | None = None,
    port: int | None = None,
    test_command: str | None = None,
    worker_timeout_s: float = DEFAULT_WORKER_TIMEOUT_S,
    session_factory=None,
) -> DeliveryResult:
    """Execute the full delivery loop for one requirement.

    Every step is durable: the work order, audit events, evidence and
    deployment facts live in PostgreSQL (``session_factory`` overrides
    the engine for tests; default resolves via ``EDS_DATABASE_URL``).
    """
    work_order_id = new_work_order_id()
    if session_factory is not None:
        control_state.configure(session_factory)
    base_dir = (
        Path(work_dir).resolve() if work_dir is not None else sandbox_manager.work_dir()
    )
    base_dir.mkdir(parents=True, exist_ok=True)
    resolved_repo_url = repo_url or _resolve_repo_url(base_dir)
    update_work_order(
        work_order_id,
        original_request=requirement,
        confirmed_requirement=requirement,
        acceptance_criteria=list(acceptance_criteria),
        repository=resolved_repo_url,
        overall_status="in_progress",
    )
    result = DeliveryResult(work_order_id=work_order_id, requirement=requirement,
                            repo_url=resolved_repo_url)
    _log(f"work order {work_order_id}: {requirement}")

    runtime = create_worker_runtime(work_order_id, base_dir=base_dir)
    _log(f"sandbox ready: {runtime['sandbox_path']}")

    project = resolve_project(work_order_id)
    repo_dir = repository.worker_repo_dir(work_order_id, base_dir=base_dir)
    result.baseline_commit = repository.checkout(
        work_order_id, project["repository"], None, repo_dir=repo_dir
    )
    update_work_order(work_order_id, baseline_commit=result.baseline_commit)
    _log(f"checked out baseline {result.baseline_commit[:12]}")

    task = WorkerTask(
        requirement=requirement,
        workspace=repo_dir,
        acceptance_criteria=tuple(acceptance_criteria),
        test_command=test_command or "uv run pytest -q",
    )
    active_worker = worker or CodexWorkerDriver()
    run_worker_task(work_order_id, task, worker=active_worker)
    _log(f"worker turn started ({type(active_worker).__name__})")

    deadline = time.monotonic() + worker_timeout_s
    while True:
        status = get_worker_status(work_order_id)
        if status["status"] in ("done", "failed"):
            break
        if time.monotonic() > deadline:
            active_worker_timeout = f"worker timed out after {worker_timeout_s}s"
            result.worker_status = "failed"
            result.worker_error = active_worker_timeout
            result.overall_status = "failed"
            mark_failed(work_order_id, active_worker_timeout)
            _log(active_worker_timeout)
            return result
        time.sleep(POLL_INTERVAL_S)
    result.worker_status = status["status"]
    result.worker_summary = status["summary"]
    result.worker_error = status["error"]
    _log(f"worker {status['status']}" + (f": {status['summary']}" if status["summary"] else ""))

    if status["status"] == "failed":
        result.overall_status = "failed"
        mark_failed(work_order_id, status["error"] or "worker failed")
        _log("worker failed; no candidate to deliver")
        return result

    evidence = run_pytest_evidence(repo_dir, task.test_command)
    result.pytest_evidence = evidence
    result.evidence.append({"kind": "pytest_run", "payload": evidence})
    record_evidence(work_order_id, "pytest_run", evidence)
    _log(
        f"pytest evidence: {evidence['status']} "
        f"({evidence['passed']} passed, {evidence['failed']} failed)"
    )

    result.candidate_commit = repository.commit_candidate(
        work_order_id,
        f"feat: {requirement[:72]}",
        repo_dir=repo_dir,
    )
    update_work_order(work_order_id, candidate_commit=result.candidate_commit)
    _log(f"candidate commit {result.candidate_commit[:12]}")

    if evidence["status"] != "passed":
        result.overall_status = "failed"
        mark_failed(
            work_order_id,
            f"pytest evidence failed ({evidence['failed']} failed, "
            f"{evidence['errors']} errors)",
        )
        _log("tests failed; skipping deployment")
        return result

    deployment = deploy_candidate(
        work_order_id,
        result.candidate_commit,
        port=port,
        client=docker_client,
        base_dir=base_dir,
    )
    result.deployment_status = deployment["status"]
    result.base_url = deployment["base_url"]
    result.docs_url = deployment["docs_url"]
    result.port = deployment["port"]
    result.deployment_health = deployment["health"]
    _log(f"deployed at {deployment['base_url']} (health: {deployment['health']})")

    if deployment["health"] == "healthy":
        record_evidence(
            work_order_id,
            "deployment_check",
            {
                "base_url": deployment["base_url"],
                "docs_url": deployment["docs_url"],
                "health": "healthy",
            },
        )
        mark_complete(
            work_order_id,
            f"delivered {requirement[:60]} at {deployment['docs_url']}",
        )
        result.overall_status = "delivered"
    else:
        mark_failed(
            work_order_id,
            f"deployed at {deployment['base_url']} but health check failed",
        )
        result.overall_status = "degraded"
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: parse args, run the loop, print the /docs URL."""
    parser = argparse.ArgumentParser(
        prog="runner", description="Requirement in, deployed /docs out."
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
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_WORKER_TIMEOUT_S, help="worker timeout seconds"
    )
    args = parser.parse_args(argv)

    worker = ScriptedWorker(args.scripted) if args.scripted else None
    result = run_delivery(
        args.requirement,
        worker=worker,
        repo_url=args.repo_url,
        work_dir=args.work_dir,
        port=args.port,
        worker_timeout_s=args.timeout,
    )

    print()
    print(f"work order   : {result.work_order_id}")
    print(f"worker       : {result.worker_status}"
          + (f" ({result.worker_error})" if result.worker_error else ""))
    print(f"candidate    : {result.candidate_commit or '-'}")
    print(f"pytest       : {result.pytest_evidence['status'] if result.pytest_evidence else '-'}")
    print(f"deployment   : {result.deployment_status or '-'} "
          f"({result.deployment_health or '-'})")
    print(f"docs url     : {result.docs_url or '-'}")
    state = get_current_state(result.work_order_id)
    print(f"durable      : overall_status={state['overall_status']}, "
          f"{state['event_count']} events, {state['evidence_count']} evidence "
          f"(PostgreSQL, survives restarts)")
    return 0 if result.overall_status in ("delivered", "degraded") else 1


if __name__ == "__main__":
    sys.exit(main())
