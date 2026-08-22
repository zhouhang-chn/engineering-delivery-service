"""Tests for the deterministic fallback supervisor (env-selectable demo backend).

Drives the same supervised loop with the rule-based model instead of a
scripted LLM: happy path to completion, and failure paths (worker fail,
failing acceptance evidence → mark_failed, never deploy a red candidate).
"""

from __future__ import annotations

import sys
from pathlib import Path

from tests.helpers.fake_docker import FakeDockerClient
from tests.helpers.git_fixture import make_template_repo

REQUIREMENT = "Add a GET /hello endpoint returning {'hello': 'world'}"

GOOD_APP_PY = '''\
"""Template FastAPI service with the /hello endpoint added."""

from fastapi import FastAPI

app = FastAPI(title="Template Service")


@app.get("/")
def root() -> dict:
    """Service root."""
    return {"service": "template", "status": "ok"}


@app.get("/healthz")
def healthz() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/hello")
def hello() -> dict:
    """Requirement: greet the world."""
    return {"hello": "world"}
'''

GOOD_TEST_PY = '''\
"""Worker-added test for the /hello requirement."""

from fastapi.testclient import TestClient

from app.main import app


def test_hello() -> None:
    assert TestClient(app).get("/hello").json() == {"hello": "world"}
'''

# the worker ships a test that fails: acceptance evidence must stop delivery
RED_TEST_PY = '''\
"""A failing acceptance test the worker shipped."""

from fastapi.testclient import TestClient

from app.main import app


def test_hello_wrong_expectation() -> None:
    assert TestClient(app).get("/hello").json() == {"hello": "universe"}
'''


def _setup(durable_db, tmp_path: Path, work_order_id: str, worker_script, fake_docker) -> None:
    from agent.supervisor import configure_supervisor
    from codex.worker_driver import ScriptedWorker
    from tools.work_order import update_work_order

    template = make_template_repo(tmp_path / "template-src")
    update_work_order(
        work_order_id,
        original_request=REQUIREMENT,
        confirmed_requirement=REQUIREMENT,
        acceptance_criteria=["GET /hello returns 200 with {'hello': 'world'}"],
        repository=str(template),
        overall_status="in_progress",
    )
    configure_supervisor(
        worker=ScriptedWorker(worker_script),
        docker_client=fake_docker,
        base_dir=tmp_path / "work",
        test_command=f"{sys.executable} -m pytest -q",
        repo_url=str(template),
    )


def test_deterministic_supervisor_completes_delivery(tmp_path: Path, durable_db) -> None:
    from agent.deterministic import deterministic_llm_factory
    from agent.runner import supervise
    from agent.supervisor import reset_supervisor_config
    from tests.helpers.db import new_id

    work_order_id = new_id()
    _setup(
        durable_db,
        tmp_path,
        work_order_id,
        [
            {"action": "status", "status": "running"},
            {"action": "write_file", "path": "app/main.py", "content": GOOD_APP_PY},
            {"action": "write_file", "path": "tests/test_hello.py", "content": GOOD_TEST_PY},
            {"action": "status", "status": "done", "summary": "added GET /hello"},
        ],
        FakeDockerClient(),
    )
    try:
        result = supervise(
            work_order_id, llm=deterministic_llm_factory(work_order_id), turn_budget=30
        )
    finally:
        reset_supervisor_config()

    assert result.overall_status == "complete", result
    assert result.deployment["health"] == "healthy"
    assert result.worker["candidate_commit"]


def test_deterministic_supervisor_never_deploys_red_candidate(
    tmp_path: Path, durable_db
) -> None:
    from agent.deterministic import deterministic_llm_factory
    from agent.runner import supervise
    from agent.supervisor import reset_supervisor_config
    from tests.helpers.db import event_types, new_id

    work_order_id = new_id()
    fake_docker = FakeDockerClient()
    _setup(
        durable_db,
        tmp_path,
        work_order_id,
        [
            {"action": "status", "status": "running"},
            {"action": "write_file", "path": "app/main.py", "content": GOOD_APP_PY},
            {"action": "write_file", "path": "tests/test_red.py", "content": RED_TEST_PY},
            {"action": "status", "status": "done", "summary": "shipped a red test"},
        ],
        fake_docker,
    )
    try:
        result = supervise(
            work_order_id, llm=deterministic_llm_factory(work_order_id), turn_budget=30
        )
    finally:
        reset_supervisor_config()

    assert result.overall_status == "failed"
    assert "acceptance tests failed" in (result.reason or "")
    assert fake_docker.builds == []  # never deployed the red candidate
    types_ = event_types(durable_db, work_order_id)
    assert "work_order.marked_failed" in types_
    assert "deployment.deployed" not in types_
