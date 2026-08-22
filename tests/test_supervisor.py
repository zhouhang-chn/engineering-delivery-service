"""Contract tests for the ReAct Supervisor (v0.1.3 core behavior).

Drives the Supervisor with a scripted LLM over the real Delivery
Control tools + ScriptedWorker + fake docker: work order → runtime →
checkout → worker turn → acceptance tests → candidate commit → deploy
→ mark_complete, all decisions made by the agent and audited as
``supervisor_turn`` events. No real LLM, Codex or docker required.
"""

from __future__ import annotations

import sys
from pathlib import Path

from tests.helpers.fake_docker import FakeDockerClient
from tests.helpers.git_fixture import make_template_repo
from tests.helpers.scripted_llm import ScriptedLlm

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
    {
        "action": "event",
        "type": "command",
        "payload": {"command": "pytest -q", "exit_code": 0},
    },
    {"action": "status", "status": "done", "summary": "added GET /hello endpoint"},
]

FAILING_WORKER_SCRIPT = [
    {"action": "status", "status": "running"},
    {"action": "fail", "error": "codex quota exceeded"},
]

REQUIREMENT = "Add a GET /hello endpoint returning {'hello': 'world'}"
CRITERIA = ["GET /hello returns 200 with {'hello': 'world'}"]


def _durable_worker_status(work_order_id: str) -> str:
    """Read the real durable worker status (drives reactive poll steps)."""
    from tools.worker import get_worker_status

    return get_worker_status(work_order_id)["status"]


def _happy_path_script(work_order_id: str) -> list[dict]:
    """Agent steps that drive a healthy work order to completion."""
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
        {"text": "worker done, acceptance green, deployed healthy; finished"},
    ]


def _setup_work_order(durable_db, tmp_path: Path, work_order_id: str) -> str:
    """Create the work order row over the template repo; return repo url."""
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
    return str(template)


def _configure(durable_db, tmp_path: Path, fake_docker: FakeDockerClient, worker) -> None:
    """Point the supervisor tool wrappers at the test doubles."""
    from agent.supervisor import configure_supervisor

    configure_supervisor(
        worker=worker,
        docker_client=fake_docker,
        base_dir=tmp_path / "work",
        test_command=f"{sys.executable} -m pytest -q",
    )


def test_build_supervisor_registers_tools_instruction_and_model(monkeypatch) -> None:
    from agent.supervisor import TOOL_FUNCTIONS, build_supervisor, load_supervisor_instruction

    agent = build_supervisor()
    tool_names = {t.__name__ for t in TOOL_FUNCTIONS}
    for expected in (
        "get_current_state",
        "get_work_order",
        "create_worker_runtime",
        "checkout_baseline",
        "start_worker_turn",
        "get_worker_status",
        "run_acceptance_tests",
        "commit_candidate",
        "deploy_candidate",
        "get_deployment_status",
        "record_evidence",
        "mark_complete",
        "mark_failed",
    ):
        assert expected in tool_names
    assert agent.name == "eds_supervisor"
    # instruction comes from the prompt file, not a hardcoded string
    instruction = load_supervisor_instruction()
    assert agent.instruction == instruction
    assert "acceptance criteria" in instruction.lower()

    # model: llm override wins, then EDS_LLM_MODEL, then the default
    fake = ScriptedLlm(steps=[{"text": "x"}], status_fn=_durable_worker_status)
    assert build_supervisor(llm=fake).model is fake
    monkeypatch.setenv("EDS_LLM_MODEL", "gemini-test-pro")
    assert build_supervisor().model == "gemini-test-pro"


def test_supervisor_completes_scripted_work_order(tmp_path: Path, durable_db) -> None:
    from agent.runner import DEFAULT_TURN_BUDGET, supervise
    from agent.supervisor import reset_supervisor_config
    from codex.worker_driver import ScriptedWorker
    from tests.helpers.db import event_types, evidence_kinds, new_id

    work_order_id = new_id()
    _setup_work_order(durable_db, tmp_path, work_order_id)
    fake_docker = FakeDockerClient()
    _configure(durable_db, tmp_path, fake_docker, ScriptedWorker(WORKER_SCRIPT))
    llm = ScriptedLlm(
        steps=_happy_path_script(work_order_id), status_fn=_durable_worker_status
    )
    try:
        result = supervise(work_order_id, llm=llm, turn_budget=DEFAULT_TURN_BUDGET)
    finally:
        reset_supervisor_config()

    assert result.overall_status == "complete"
    assert result.terminal is True
    assert result.turns >= 1
    # the deployment is real (fake-docker backed): one build, one run, healthy
    assert len(fake_docker.builds) == 1
    assert len(fake_docker.runs) == 1
    deployed_port = fake_docker.runs[0]["ports"]["8000/tcp"]
    assert result.deployment["docs_url"] == f"http://localhost:{deployed_port}/docs"
    assert result.deployment["health"] == "healthy"

    # durable acceptance: state, evidence, artifacts
    from tools.work_order import get_current_state

    state = get_current_state(work_order_id)
    assert state["worker"]["status"] == "done"
    assert state["worker"]["candidate_commit"]
    assert state["deployment"]["health"] == "healthy"
    kinds = evidence_kinds(durable_db, work_order_id)
    assert "pytest_run" in kinds
    assert "deployment_check" in kinds
    types_ = event_types(durable_db, work_order_id)
    assert types_.count("supervisor_turn") >= 1
    for expected in (
        "runtime.worker_created",
        "worker.turn_started",
        "deployment.deployed",
        "work_order.marked_complete",
    ):
        assert expected in types_


def test_supervisor_recovers_from_wrong_order_deploy(tmp_path: Path, durable_db) -> None:
    from agent.runner import supervise
    from agent.supervisor import reset_supervisor_config
    from codex.worker_driver import ScriptedWorker
    from tests.helpers.db import new_id

    work_order_id = new_id()
    _setup_work_order(durable_db, tmp_path, work_order_id)
    fake_docker = FakeDockerClient()
    _configure(durable_db, tmp_path, fake_docker, ScriptedWorker(WORKER_SCRIPT))
    # wrong order first: deploy an invented commit before any candidate exists
    script = [
        {
            "tool": "deploy_candidate",
            "args": {"work_order_id": work_order_id, "candidate_commit": "deadbeef"},
        },
        {"tool": "get_current_state", "args": {"work_order_id": work_order_id}},
    ] + _happy_path_script(work_order_id)[1:]
    llm = ScriptedLlm(
        steps=script, status_fn=_durable_worker_status
    )
    try:
        result = supervise(work_order_id, llm=llm, turn_budget=10)
    finally:
        reset_supervisor_config()

    # observed the failure, recovered, delivered anyway
    assert result.overall_status == "complete"
    assert len(fake_docker.builds) == 1  # the premature deploy never built


def test_supervisor_marks_failed_on_budget_exhaustion(tmp_path: Path, durable_db) -> None:
    from agent.runner import supervise
    from agent.supervisor import reset_supervisor_config
    from tests.helpers.db import event_types, new_id

    work_order_id = new_id()
    _setup_work_order(durable_db, tmp_path, work_order_id)
    _configure(durable_db, tmp_path, FakeDockerClient(), worker=None)
    llm = ScriptedLlm(
        steps=[{"text": "still thinking..."}] * 5, status_fn=_durable_worker_status
    )
    try:
        result = supervise(work_order_id, llm=llm, turn_budget=3)
    finally:
        reset_supervisor_config()

    assert result.overall_status == "failed"
    assert result.terminal is True
    assert result.turns == 3
    assert "turn budget" in (result.reason or "")
    types_ = event_types(durable_db, work_order_id)
    assert types_.count("supervisor_turn") == 3
    assert "work_order.marked_failed" in types_


def test_supervisor_marks_failed_when_worker_fails(tmp_path: Path, durable_db) -> None:
    from agent.runner import supervise
    from agent.supervisor import reset_supervisor_config
    from codex.worker_driver import ScriptedWorker
    from tests.helpers.db import new_id

    work_order_id = new_id()
    _setup_work_order(durable_db, tmp_path, work_order_id)
    fake_docker = FakeDockerClient()
    _configure(
        durable_db, tmp_path, fake_docker, ScriptedWorker(FAILING_WORKER_SCRIPT)
    )
    script = [
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
        {"text": "worker failed; no candidate to deliver"},
    ]
    llm = ScriptedLlm(steps=script, status_fn=_durable_worker_status)
    try:
        result = supervise(work_order_id, llm=llm, turn_budget=10)
    finally:
        reset_supervisor_config()

    assert result.overall_status == "failed"
    assert result.terminal is True
    assert "codex quota exceeded" in (result.reason or "")
    assert fake_docker.builds == []  # never deployed anything
