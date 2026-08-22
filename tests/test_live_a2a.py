"""Live A2A tests (marked): real HTTP server, raw client, real Docker.

- ``docker``: a real uvicorn endpoint process, raw httpx JSON-RPC calls
  (the way an external caller would), ScriptedWorker + scripted LLM,
  real Docker build/run/health of the candidate. Run: ``uv run pytest
  -m docker``
- ``llm`` + ``codex``: the true full chain — real model deciding every
  step, real Codex worker turn, real Docker. Run: ``uv run pytest -m
  'llm and codex'`` (skips without credentials).
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

from tests.helpers.git_fixture import make_template_repo
from tests.helpers.scripted_llm import ScriptedLlm

REQUIREMENT = "Add a GET /hello endpoint returning {'hello': 'world'}"

POLL_TIMEOUT_S = 300.0
POLL_INTERVAL_S = 1.0

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


def _worker_script() -> list[dict]:
    return [
        {"action": "status", "status": "running"},
        {"action": "write_file", "path": "app/main.py", "content": WORKER_APP_PY},
        {"action": "write_file", "path": "tests/test_hello.py", "content": WORKER_TEST_PY},
        {"action": "status", "status": "done", "summary": "added GET /hello endpoint"},
    ]


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


def _durable_worker_status(work_order_id: str) -> str:
    from tools.worker import get_worker_status

    return get_worker_status(work_order_id)["status"]


def _configure_backend(durable_db, tmp_path: Path, worker) -> None:
    from agent.supervisor import configure_supervisor

    template = make_template_repo(tmp_path / "template-src")
    configure_supervisor(
        worker=worker,
        base_dir=tmp_path / "work",
        test_command=f"{sys.executable} -m pytest -q",
        repo_url=str(template),
        llm_factory=lambda wo: ScriptedLlm(
            steps=_supervisor_script(wo), status_fn=_durable_worker_status
        ),
    )


def _start_endpoint() -> tuple[str, object]:
    """Run the real uvicorn endpoint on a free port; return (url, server)."""

    import uvicorn

    from a2a_api.server import create_app
    from deployment.docker import free_port

    port = free_port()
    config = uvicorn.Config(
        create_app(), host="127.0.0.1", port=port, log_level="warning"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="eds-a2a-live")
    thread.start()
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{base}/healthz", timeout=2.0).status_code == 200:
                return base, server
        except httpx.HTTPError:
            time.sleep(0.2)
    pytest.fail("live A2A endpoint did not come up in time")


def _send(base: str, requirement: str) -> dict:
    response = httpx.post(
        base,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": "msg-live-1",
                    "role": "user",
                    "parts": [{"kind": "text", "text": requirement}],
                }
            },
        },
        timeout=60.0,
    )
    body = response.json()
    assert "error" not in body, body
    return body["result"]


def _get_task(base: str, task_id: str) -> dict:
    response = httpx.post(
        base,
        json={"jsonrpc": "2.0", "id": 2, "method": "tasks/get", "params": {"id": task_id}},
        timeout=30.0,
    )
    body = response.json()
    assert "error" not in body, body
    return body["result"]


def _poll_terminal(base: str, task_id: str) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        task = _get_task(base, task_id)
        if task["status"]["state"] in ("completed", "failed"):
            return task
        time.sleep(POLL_INTERVAL_S)
    pytest.fail(f"task {task_id} did not reach a terminal state in time")


def _cleanup_container(work_order_id: str) -> None:
    import docker.errors

    from deployment import docker as deploy_mod

    try:
        deploy_mod.default_client().containers.get(f"eds-{work_order_id}").remove(force=True)
    except docker.errors.NotFound:
        pass
    except OSError:
        pass


@pytest.mark.docker
def test_a2a_http_endpoint_full_delivery_with_real_docker(
    tmp_path: Path, durable_db
) -> None:
    """Raw httpx A2A call → supervised delivery → real Docker + /docs."""
    from codex.worker_driver import ScriptedWorker

    _configure_backend(durable_db, tmp_path, ScriptedWorker(_worker_script()))
    base, server = _start_endpoint()
    try:
        task = _send(base, REQUIREMENT)
        final = _poll_terminal(base, task["id"])
        assert final["status"]["state"] == "completed", final
        artifacts = {a["name"]: a for a in final["artifacts"]}
        docs_url = artifacts["docs_url"]["parts"][0]["text"]
        docs = httpx.get(docs_url, timeout=30.0, follow_redirects=True)
        assert docs.status_code == 200
        assert "swagger" in docs.text.lower()
        hello_url = docs_url.rsplit("/", 1)[0] + "/hello"
        assert httpx.get(hello_url, timeout=10.0).json() == {"hello": "world"}
    finally:
        if "task" in locals():
            _cleanup_container(task["id"])
        server.should_exit = True


@pytest.mark.llm
@pytest.mark.codex
def test_a2a_full_chain_real_llm_and_codex(tmp_path: Path, durable_db) -> None:
    """The real chain: real model + real Codex worker + real Docker."""
    import os

    if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_GENAI_USE_VERTEXAI")):
        pytest.skip("no LLM credentials: set GOOGLE_API_KEY (or configure Vertex ADC)")

    from agent.supervisor import configure_supervisor

    configure_supervisor(base_dir=tmp_path / "work", llm_factory=None)
    base, server = _start_endpoint()
    task_id = None
    try:
        task = _send(base, "Add a GET /eds-live endpoint returning {'eds': 'live'}")
        task_id = task["id"]
        final = _poll_terminal(base, task_id)
        assert final["status"]["state"] == "completed", final
        artifacts = {a["name"]: a for a in final["artifacts"]}
        docs_url = artifacts["docs_url"]["parts"][0]["text"]
        docs = httpx.get(docs_url, timeout=30.0, follow_redirects=True)
        assert docs.status_code == 200
    finally:
        if task_id:
            _cleanup_container(task_id)
        server.should_exit = True
