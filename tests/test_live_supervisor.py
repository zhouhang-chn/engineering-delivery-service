"""Live supervisor runs (marked): real infrastructure, no LLM double.

Two layers, both excluded from default runs:

- ``docker``: real Docker build/run/health-check of the deployed
  candidate, ScriptedWorker, scripted LLM — everything real except the
  model. Run: ``uv run pytest -m docker``
- ``llm``: additionally the real model (``EDS_LLM_MODEL`` /
  ``GOOGLE_API_KEY`` / Vertex ADC). Run: ``uv run pytest -m llm``
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from tests.helpers.git_fixture import make_template_repo
from tests.helpers.scripted_llm import ScriptedLlm

REQUIREMENT = "Add a GET /hello endpoint returning {'hello': 'world'}"
CRITERIA = ["GET /hello returns 200 with {'hello': 'world'}"]


def _durable_worker_status(work_order_id: str) -> str:
    from tools.worker import get_worker_status

    return get_worker_status(work_order_id)["status"]


def _worker_script() -> list[dict]:
    """ScriptedWorker turns the template into the /hello service."""
    app_py = (
        '"""Template FastAPI service with the /hello endpoint added."""\n\n'
        "from fastapi import FastAPI\n\n"
        'app = FastAPI(title="Template Service")\n\n\n'
        '@app.get("/")\n'
        "def root() -> dict:\n"
        '    """Service root: identify the service and its status."""\n'
        '    return {"service": "template", "status": "ok"}\n\n\n'
        '@app.get("/healthz")\n'
        "def healthz() -> dict:\n"
        '    """Liveness probe consumed by the deployment health check."""\n'
        '    return {"status": "ok"}\n\n\n'
        '@app.get("/hello")\n'
        "def hello() -> dict:\n"
        '    """Requirement: greet the world."""\n'
        '    return {"hello": "world"}\n'
    )
    test_py = (
        '"""Worker-added test for the /hello requirement."""\n\n'
        "from fastapi.testclient import TestClient\n\n"
        "from app.main import app\n\n\n"
        "def test_hello() -> None:\n"
        '    assert TestClient(app).get("/hello").json() == {"hello": "world"}\n'
    )
    return [
        {"action": "status", "status": "running"},
        {"action": "write_file", "path": "app/main.py", "content": app_py},
        {"action": "write_file", "path": "tests/test_hello.py", "content": test_py},
        {"action": "status", "status": "done", "summary": "added GET /hello endpoint"},
    ]


def _supervisor_script(work_order_id: str) -> list[dict]:
    """Agent steps that drive the work order to completion."""
    return [
        {"tool": "get_current_state", "args": {"work_order_id": work_order_id}},
        {"tool": "create_worker_runtime", "args": {"work_order_id": work_order_id}},
        {"tool": "checkout_baseline", "args": {"work_order_id": work_order_id}},
        {"tool": "start_worker_turn", "args": {"work_order_id": work_order_id}},
        {"poll_worker": "done", "work_order_id": work_order_id},
        {"tool": "run_acceptance_tests", "args": {"work_order_id": work_order_id}},
        {"tool": "commit_candidate", "args": {"work_order_id": work_order_id}},
        {"tool": "deploy_candidate", "args": {"work_order_id": work_order_id}},
        {
            "tool": "mark_complete",
            "args": {
                "work_order_id": work_order_id,
                "summary": "delivered /hello; acceptance green; deployed healthy",
            },
        },
        {"text": "delivered"},
    ]


def _setup_work_order(durable_db, tmp_path: Path, work_order_id: str) -> None:
    from tools.work_order import update_work_order

    template = make_template_repo(tmp_path / "template-src")
    update_work_order(
        work_order_id,
        original_request=REQUIREMENT,
        confirmed_requirement=REQUIREMENT,
        acceptance_criteria=CRITERIA,
        repository=str(template),
        overall_status="in_progress",
    )


def _fetch_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status == 200
    except OSError:
        return False


def _cleanup_container(work_order_id: str) -> None:
    """Remove the deployed container (real-docker tests must not leak)."""
    import docker.errors

    from deployment import docker as deploy_mod

    try:
        deploy_mod.default_client().containers.get(f"eds-{work_order_id}").remove(force=True)
    except docker.errors.NotFound:
        pass
    except OSError:
        pass


def _run_supervision(durable_db, tmp_path: Path, work_order_id: str, llm) -> None:
    from agent.runner import supervise
    from agent.supervisor import configure_supervisor, reset_supervisor_config
    from codex.worker_driver import ScriptedWorker

    configure_supervisor(
        worker=ScriptedWorker(_worker_script()),
        base_dir=tmp_path / "work",
        test_command=f"{sys.executable} -m pytest -q",
    )
    try:
        result = supervise(work_order_id, llm=llm, turn_budget=25)

        assert result.overall_status == "complete", result
        assert result.deployment["health"] == "healthy", result.deployment
        assert result.deployment["docs_url"]
        # the deployed /docs really answers
        for _ in range(10):
            if _fetch_ok(result.deployment["docs_url"]):
                break
            time.sleep(1.0)
        else:
            pytest.fail(f"docs url never answered: {result.deployment['docs_url']}")

        from tests.helpers.db import evidence_kinds

        kinds = evidence_kinds(durable_db, work_order_id)
        assert "pytest_run" in kinds and "deployment_check" in kinds
    finally:
        reset_supervisor_config()
        _cleanup_container(work_order_id)


@pytest.mark.docker
def test_supervisor_drives_real_docker_deploy(tmp_path: Path, durable_db) -> None:
    """Everything real except the model: Docker build/run + health + /docs."""
    from tests.helpers.db import new_id

    work_order_id = new_id()
    _setup_work_order(durable_db, tmp_path, work_order_id)
    llm = ScriptedLlm(
        steps=_supervisor_script(work_order_id), status_fn=_durable_worker_status
    )
    _run_supervision(durable_db, tmp_path, work_order_id, llm)


@pytest.mark.llm
def test_live_supervisor_real_llm_delivers(tmp_path: Path, durable_db) -> None:
    """Real model decides every step; ScriptedWorker + real Docker."""
    has_key = os.environ.get("GOOGLE_API_KEY")
    has_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") == "true"
    if not (has_key or has_vertex):
        pytest.skip(
            "no LLM credentials: set GOOGLE_API_KEY (or configure Vertex ADC)"
        )

    from agent.runner import supervise
    from agent.supervisor import configure_supervisor, reset_supervisor_config
    from codex.worker_driver import ScriptedWorker
    from tests.helpers.db import event_types, new_id

    work_order_id = new_id()
    _setup_work_order(durable_db, tmp_path, work_order_id)
    configure_supervisor(
        worker=ScriptedWorker(_worker_script()),
        base_dir=tmp_path / "work",
        test_command=f"{sys.executable} -m pytest -q",
    )
    _log_script_path = tmp_path / "supervisor_events.json"
    try:
        result = supervise(work_order_id, turn_budget=25)
    finally:
        reset_supervisor_config()
        _cleanup_container(work_order_id)
        from db.models import Event

        with durable_db() as session:
            rows = (
                session.query(Event)
                .filter_by(work_order_id=work_order_id)
                .order_by(Event.id)
                .all()
            )
            events = [
                {"type": row.type, "payload": row.payload, "created_at": str(row.created_at)}
                for row in rows
            ]
        _log_script_path.write_text(json.dumps(events, indent=2, default=str))

    assert result.overall_status == "complete", result
    assert result.deployment["health"] == "healthy", result.deployment
    types_ = event_types(durable_db, work_order_id)
    assert "supervisor_turn" in types_
    assert "work_order.marked_complete" in types_
