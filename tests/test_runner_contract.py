"""Contract test for the runner loop (v0.1.1 core behavior).

Drives the full delivery path — work order → sandbox → checkout → worker
turn (ScriptedWorker) → pytest evidence → candidate commit → docker deploy
→ health check → /docs URL — with a fake docker client. No Codex and no
real docker required.
"""

from __future__ import annotations

import sys
from pathlib import Path

from tests.helpers.fake_docker import FakeDockerClient
from tests.helpers.git_fixture import make_template_repo

WORKER_APP_PY = '''\
"""Template FastAPI service with the /hello endpoint added."""

from fastapi import FastAPI

app = FastAPI(title="Template Service")


@app.get("/")
def root() -> dict:
    """Service root: identify the service and its status."""
    return {"service": "template", "status": "ok"}


@app.get("/healthz")
def healthz() -> dict:
    """Liveness probe consumed by the deployment health check."""
    return {"status": "ok"}


@app.get("/hello")
def hello() -> dict:
    """Requirement: greet the world."""
    return {"hello": "world"}
'''

WORKER_TEST_PY = '''\
"""Worker-added test for the /hello requirement."""

from fastapi.testclient import TestClient

from app.main import app


def test_hello() -> None:
    assert TestClient(app).get("/hello").json() == {"hello": "world"}
'''

SCRIPT = [
    {"action": "status", "status": "running"},
    {
        "action": "write_file",
        "path": "app/main.py",
        "content": WORKER_APP_PY,
    },
    {
        "action": "write_file",
        "path": "tests/test_hello.py",
        "content": WORKER_TEST_PY,
    },
    {
        "action": "event",
        "type": "command",
        "payload": {"command": "pytest -q", "exit_code": 0},
    },
    {"action": "status", "status": "done", "summary": "added GET /hello endpoint"},
]


def test_pytest_summary_parses_counts_behind_warning_noise() -> None:
    from runner import _parse_pytest_summary

    stdout = "...\n3 passed, 1 warning in 0.20s\n"
    parsed = _parse_pytest_summary(stdout)
    assert parsed["passed"] == 3
    assert parsed["failed"] == 0
    assert parsed["summary_line"].startswith("3 passed")

    mixed = "1 failed, 2 passed in 1.00s"
    parsed = _parse_pytest_summary(mixed)
    assert parsed["passed"] == 2
    assert parsed["failed"] == 1

    empty = _parse_pytest_summary("")
    assert empty["passed"] == 0 and empty["summary_line"] == ""


def test_runner_scripted_loop_produces_deployed_docs_url(
    tmp_path: Path, durable_db, db_engine
) -> None:
    from codex.worker_driver import ScriptedWorker
    from runner import run_delivery
    from tools.work_order import get_current_state

    template = make_template_repo(tmp_path / "template-src")
    fake_docker = FakeDockerClient()

    result = run_delivery(
        "Add a GET /hello endpoint returning {'hello': 'world'}",
        acceptance_criteria=["GET /hello returns 200 with {'hello': 'world'}"],
        worker=ScriptedWorker(SCRIPT),
        docker_client=fake_docker,
        repo_url=str(template),
        work_dir=tmp_path / "work",
        test_command=f"{sys.executable} -m pytest -q",
        session_factory=durable_db,
    )

    # worker reached done and its summary was captured
    assert result.worker_status == "done"
    assert result.worker_summary == "added GET /hello endpoint"

    # independent pytest evidence was recorded and passed
    assert result.pytest_evidence["status"] == "passed"
    assert result.pytest_evidence["passed"] >= 3

    # candidate commit exists, on the candidate branch, differing from baseline
    assert result.candidate_commit
    assert result.baseline_commit
    assert result.candidate_commit != result.baseline_commit

    # deployment: image built from the workspace, container on the chosen port
    assert len(fake_docker.builds) == 1
    assert fake_docker.builds[0]["tag"].startswith("eds/")
    assert len(fake_docker.runs) == 1
    assert fake_docker.runs[0]["ports"] == {"8000/tcp": result.port}
    assert result.deployment_status == "deployed"
    assert result.deployment_health == "healthy"
    assert result.docs_url == f"http://localhost:{result.port}/docs"

    # v0.1.2: the whole flow is durable — same facts via get_current_state
    state = get_current_state(result.work_order_id)
    assert state["overall_status"] == "complete"
    assert state["worker"]["status"] == "done"
    assert state["worker"]["summary"] == "added GET /hello endpoint"
    assert state["worker"]["candidate_commit"] == result.candidate_commit
    assert state["deployment"]["docs_url"] == result.docs_url
    assert state["deployment"]["health"] == "healthy"
    assert state["requirement"]["acceptance_criteria"] == [
        "GET /hello returns 200 with {'hello': 'world'}"
    ]

    from tests.helpers.db import evidence_kinds

    kinds = evidence_kinds(durable_db, result.work_order_id)
    assert "pytest_run" in kinds and "deployment_check" in kinds

    from tests.helpers.db import event_types

    flow_types = event_types(durable_db, result.work_order_id)
    for expected in (
        "work_order.created",
        "runtime.worker_created",
        "deployment.deployed",
        "work_order.marked_complete",
    ):
        assert expected in flow_types

    # restart-inspectable: a fresh process would re-read the same snapshot
    before = get_current_state(result.work_order_id)
    db_engine.dispose()
    assert get_current_state(result.work_order_id) == before
