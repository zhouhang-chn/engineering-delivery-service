"""Contract tests for the A2A endpoint (v0.1.4 core behavior).

Exercises the endpoint the way an external caller would: JSON-RPC
``message/send`` over HTTP → background supervised delivery (scripted
LLM + ScriptedWorker + fake docker) → poll ``tasks/get`` until the
task maps the durable work-order state to A2A task states with
artifacts. No real LLM, Codex or docker required.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from tests.helpers.fake_docker import FakeDockerClient
from tests.helpers.git_fixture import make_template_repo
from tests.helpers.scripted_llm import ScriptedLlm

REQUIREMENT = "Add a GET /hello endpoint returning {'hello': 'world'}"
CRITERIA = ["GET /hello returns 200 with {'hello': 'world'}"]

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

WORKER_SCRIPT = [
    {"action": "status", "status": "running"},
    {"action": "write_file", "path": "app/main.py", "content": WORKER_APP_PY},
    {"action": "write_file", "path": "tests/test_hello.py", "content": WORKER_TEST_PY},
    {"action": "status", "status": "done", "summary": "added GET /hello endpoint"},
]

FAILING_WORKER_SCRIPT = [
    {"action": "status", "status": "running"},
    {"action": "fail", "error": "codex quota exceeded"},
]

POLL_TIMEOUT_S = 60.0
POLL_INTERVAL_S = 0.2


def _durable_worker_status(work_order_id: str) -> str:
    from tools.worker import get_worker_status

    return get_worker_status(work_order_id)["status"]


def _supervisor_script(work_order_id: str) -> list[dict]:
    return [
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


def _fail_worker_script(work_order_id: str) -> list[dict]:
    return [
        {"tool": "create_worker_runtime", "args": {"work_order_id": work_order_id}},
        {"tool": "checkout_baseline", "args": {"work_order_id": work_order_id}},
        {"tool": "start_worker_turn", "args": {"work_order_id": work_order_id}},
        {"poll_worker": "failed", "work_order_id": work_order_id},
        {
            "tool": "mark_failed",
            "args": {
                "work_order_id": work_order_id,
                "reason": "worker failed: codex quota exceeded",
            },
        },
        {"text": "worker failed"},
    ]


def _configure_backend(durable_db, tmp_path: Path, worker, fail: bool = False):
    """Wire the supervisor backend to test doubles; return the app."""
    from a2a_api.server import create_app
    from agent.supervisor import configure_supervisor, reset_supervisor_config

    template = make_template_repo(tmp_path / "template-src")
    configure_supervisor(
        worker=worker,
        docker_client=FakeDockerClient(),
        base_dir=tmp_path / "work",
        test_command=f"{sys.executable} -m pytest -q",
        repo_url=str(template),
        llm_factory=lambda work_order_id: ScriptedLlm(
            steps=(
                _fail_worker_script(work_order_id)
                if fail
                else _supervisor_script(work_order_id)
            ),
            status_fn=_durable_worker_status,
        ),
    )
    app = create_app()
    client = TestClient(app)
    reset = reset_supervisor_config
    return client, reset


def _send_requirement(client: TestClient, text: str) -> dict:
    response = client.post(
        "/",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": "msg-test-1",
                    "role": "user",
                    "parts": [{"kind": "text", "text": text}],
                }
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "error" not in body, body
    return body["result"]


def _get_task(client: TestClient, task_id: str) -> dict:
    response = client.post(
        "/",
        json={"jsonrpc": "2.0", "id": 2, "method": "tasks/get", "params": {"id": task_id}},
    )
    assert response.status_code == 200
    body = response.json()
    assert "error" not in body, body
    return body["result"]


def _poll_terminal(client: TestClient, task_id: str) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        task = _get_task(client, task_id)
        if task["status"]["state"] in ("completed", "failed"):
            return task
        time.sleep(POLL_INTERVAL_S)
    pytest_fail_timeout(task_id)


def pytest_fail_timeout(task_id: str) -> None:
    import pytest

    pytest.fail(f"task {task_id} did not reach a terminal state in time")


def test_agent_card_advertises_delivery_skill() -> None:
    from a2a_api.server import create_app

    client = TestClient(create_app())
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    card = response.json()
    assert card["name"] == "Engineering Delivery Agent"
    assert card["capabilities"].get("stateTransitionHistory") is not None
    skills = card["skills"]
    assert any("FastAPI" in skill["name"] or "fastapi" in skill["id"] for skill in skills)


def test_message_send_creates_task_in_working_state(tmp_path: Path, durable_db) -> None:
    client, reset = _configure_backend(
        durable_db, tmp_path, worker=_scripted_worker_done_slowly()
    )
    try:
        task = _send_requirement(client, REQUIREMENT)
        assert task["id"].startswith("wo-")
        assert task["status"]["state"] in ("submitted", "working")
    finally:
        reset()


def _scripted_worker_done_slowly():
    """A worker that finishes after a short delay so 'working' is observable."""
    from codex.worker_driver import ScriptedWorker

    return ScriptedWorker(
        [
            {"action": "status", "status": "running"},
            {"action": "sleep", "seconds": 1.0},
        ]
        + WORKER_SCRIPT[1:]
    )


def test_task_lifecycle_completes_with_artifacts(tmp_path: Path, durable_db) -> None:
    from codex.worker_driver import ScriptedWorker

    client, reset = _configure_backend(
        durable_db, tmp_path, worker=ScriptedWorker(WORKER_SCRIPT)
    )
    try:
        task = _send_requirement(client, REQUIREMENT + " with criteria: " + CRITERIA[0])
        final = _poll_terminal(client, task["id"])
        assert final["status"]["state"] == "completed"

        artifacts = {a["name"]: a for a in final.get("artifacts", [])}
        assert "docs_url" in artifacts
        assert artifacts["docs_url"]["parts"][0]["text"].endswith("/docs")
        assert "deployment_url" in artifacts
        assert "repository" in artifacts
        assert "@" in artifacts["repository"]["parts"][0]["text"]
        assert "pytest_evidence" in artifacts
        assert "delivery_summary" in artifacts

        # the durable work order agrees
        from tools.work_order import get_current_state

        state = get_current_state(task["id"])
        assert state["overall_status"] == "complete"
        assert state["deployment"]["health"] == "healthy"
        assert state["requirement"]["original_request"] == REQUIREMENT + " with criteria: " + CRITERIA[0]
    finally:
        reset()


def test_failed_delivery_maps_to_failed_task_with_reason(
    tmp_path: Path, durable_db
) -> None:
    from codex.worker_driver import ScriptedWorker

    client, reset = _configure_backend(
        durable_db,
        tmp_path,
        worker=ScriptedWorker(FAILING_WORKER_SCRIPT),
        fail=True,
    )
    try:
        task = _send_requirement(client, REQUIREMENT)
        final = _poll_terminal(client, task["id"])
        assert final["status"]["state"] == "failed"
        reason = final["status"].get("message", {})
        reason_text = "".join(
            part.get("text", "") for part in reason.get("parts", [])
        )
        assert "codex quota exceeded" in reason_text
    finally:
        reset()


def test_tasks_get_unknown_task_returns_jsonrpc_error() -> None:
    from a2a_api.server import create_app

    client = TestClient(create_app())
    response = client.post(
        "/",
        json={"jsonrpc": "2.0", "id": 3, "method": "tasks/get", "params": {"id": "wo-nope"}},
    )
    body = response.json()
    assert body["error"]["code"] == -32001
    assert "not found" in body["error"]["message"].lower()


def test_message_send_with_empty_requirement_fails_task() -> None:
    from a2a_api.server import create_app

    client = TestClient(create_app())
    response = client.post(
        "/",
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": "msg-empty",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "   "}],
                }
            },
        },
    )
    body = response.json()
    assert "error" not in body, body
    task = body["result"]
    assert task["status"]["state"] == "failed"
    reason_text = "".join(
        part.get("text", "")
        for part in task["status"].get("message", {}).get("parts", [])
    )
    assert "requirement" in reason_text.lower()


def test_invalid_jsonrpc_method_returns_error() -> None:
    from a2a_api.server import create_app

    client = TestClient(create_app())
    response = client.post(
        "/", json={"jsonrpc": "2.0", "id": 5, "method": "bogus/method", "params": {}}
    )
    body = response.json()
    assert body["error"]["code"] == -32601
