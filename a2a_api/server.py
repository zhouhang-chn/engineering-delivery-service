"""A2A endpoint: EDS as one Engineering Delivery Agent.

An A2A Task maps to one Engineering Work Order, not to a Codex turn.
The endpoint is a thin JSON-RPC protocol adapter (A2A wire surface:
``message/send``, ``tasks/get``, agent card): it creates and reads
work orders exclusively through the Delivery Control tools and the
shared supervised-delivery launcher — task state always derives from
the durable ``overall_status``, never from in-memory session state.

See docs/designs/a2a-interface.md and architecture doc section 5.

Run: ``uv run python -m a2a_api.server`` (uvicorn; EDS_A2A_HOST/PORT).
"""

from __future__ import annotations

import os
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

AGENT_NAME = "Engineering Delivery Agent"
AGENT_VERSION = "0.1.0"
JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_TASK_NOT_FOUND = -32001

TASK_STATE_MAP = {
    "complete": "completed",
    "failed": "failed",
    "in_progress": "working",
    None: "submitted",
}


def task_state_from_overall(overall_status: str | None) -> str:
    """Map a work order's overall_status onto an A2A task state."""
    state = TASK_STATE_MAP.get(overall_status)
    if state is None:
        # unknown future statuses degrade to "working", never to a lie
        return "working"
    return state


def _text_part(text: str) -> dict:
    return {"kind": "text", "text": text}


def _message(text: str) -> dict:
    return {"role": "agent", "parts": [_text_part(text)], "messageId": f"msg-{uuid.uuid4().hex[:12]}"}


def _status(state: str, reason: str | None = None) -> dict:
    status: dict = {"state": state, "timestamp": _now_iso()}
    if reason is not None:
        status["message"] = _message(reason)
    return status


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _requirement_text(params: dict) -> str:
    """Extract the requirement text from message/send params."""
    message = params.get("message") or {}
    texts = [
        part.get("text", "")
        for part in message.get("parts", [])
        if part.get("kind") == "text"
    ]
    return "\n".join(text for text in texts if text).strip()


def build_artifacts(state: dict) -> list[dict]:
    """Assemble completion artifacts from durable work-order state.

    Per a2a-interface design section 4: repository/commit, deployment
    URL, /docs URL, test result, delivery summary (inspection arrives
    in v0.3).
    """
    from tools.work_order import get_work_order

    work_order = get_work_order(state["work_order_id"])
    deployment = state["deployment"]
    worker = state["worker"]
    artifacts: list[dict] = []

    def add(name: str, text: str) -> None:
        artifacts.append(
            {
                "artifactId": str(len(artifacts) + 1),
                "name": name,
                "parts": [_text_part(text)],
            }
        )

    if work_order.get("repository") or worker.get("candidate_commit"):
        repo_text = "@".join(
            x
            for x in (work_order.get("repository"), worker.get("candidate_commit"))
            if x
        )
        add("repository", repo_text)
    if deployment.get("url"):
        add("deployment_url", deployment["url"])
    if deployment.get("docs_url"):
        add("docs_url", deployment["docs_url"])
    pytest_summary = _latest_evidence_text(state["work_order_id"])
    if pytest_summary:
        add("pytest_evidence", pytest_summary)
    for artifact in reversed(state.get("artifacts") or []):
        if artifact.get("type") == "completion_summary":
            add("delivery_summary", artifact.get("summary", ""))
            break
    return artifacts


def _latest_evidence_text(work_order_id: str) -> str | None:
    """Render the latest pytest_run evidence payload as text."""
    from control.state import session_scope
    from db.models import Evidence

    with session_scope() as session:
        row = (
            session.query(Evidence)
            .filter_by(work_order_id=work_order_id, kind="pytest_run")
            .order_by(Evidence.id.desc())
            .first()
        )
        if row is None:
            return None
        payload = row.payload or {}
        return (
            f"pytest: {payload.get('status')} "
            f"({payload.get('passed', 0)} passed, {payload.get('failed', 0)} failed, "
            f"{payload.get('errors', 0)} errors) — {payload.get('summary_line')}".strip()
        )


def task_from_state(state: dict) -> dict:
    """Render one A2A Task from the durable work-order snapshot."""
    overall = state["overall_status"]
    task = {
        "id": state["work_order_id"],
        "contextId": state["work_order_id"],
        "status": _status(task_state_from_overall(overall)),
        "kind": "task",
    }
    if overall == "failed":
        task["status"] = _status("failed", _failure_reason(state))
    if overall == "complete":
        task["artifacts"] = build_artifacts(state)
    return task


def _failure_reason(state: dict) -> str:
    """Pull the persisted failure reason for the task status message."""
    for artifact in reversed(state.get("artifacts") or []):
        if artifact.get("type") == "failure_reason":
            return artifact.get("reason", "delivery failed")
    return "delivery failed"


def _handle_message_send(params: dict) -> dict:
    """Requirement text in → work order created → supervisor launched."""
    requirement = _requirement_text(params)
    if not requirement:
        return {
            "id": f"wo-{uuid.uuid4().hex[:12]}",
            "contextId": "-",
            "kind": "task",
            "status": _status("failed", "invalid requirement: no text content in message"),
        }
    from agent.runner import start_supervised_delivery

    work_order_id, _thread = start_supervised_delivery(requirement)
    from tools.work_order import get_current_state

    return task_from_state(get_current_state(work_order_id))


def _handle_tasks_get(params: dict) -> dict:
    """Task id → A2A Task rendered from durable state."""
    task_id = params.get("id") or ""
    if not task_id:
        raise JsonRpcError(JSONRPC_INVALID_PARAMS, "tasks/get requires an 'id' param")
    from tools.work_order import get_current_state

    try:
        state = get_current_state(task_id)
    except LookupError:
        raise JsonRpcError(JSONRPC_TASK_NOT_FOUND, f"task {task_id!r} not found") from None
    return task_from_state(state)


class JsonRpcError(Exception):
    """One JSON-RPC 2.0 error object."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


def agent_card(base_url: str = "") -> dict:
    """The A2A agent card: one skill, FastAPI API delivery."""
    return {
        "name": AGENT_NAME,
        "description": (
            "Autonomous engineering delivery: an A2A task carrying an API "
            "requirement becomes a deployed FastAPI service with a live /docs."
        ),
        "url": base_url or "/",
        "version": AGENT_VERSION,
        "capabilities": {
            "stateTransitionHistory": True,
            "pushNotifications": False,
            "streaming": False,
        },
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": [
            {
                "id": "fastapi-api-delivery",
                "name": "FastAPI API delivery",
                "description": (
                    "Build, test and deploy a FastAPI endpoint from a "
                    "requirement; returns the deployment and /docs URLs."
                ),
                "tags": ["fastapi", "delivery", "deployment"],
            }
        ],
    }


def create_app() -> FastAPI:
    """Build the EDS A2A application (JSON-RPC + agent card)."""
    app = FastAPI(
        title="EDS A2A Endpoint",
        description="Engineering Delivery Agent — A2A JSON-RPC surface.",
        version=AGENT_VERSION,
    )

    @app.get("/.well-known/agent-card.json")
    def get_agent_card() -> dict:
        """Serve the A2A agent card."""
        return agent_card()

    @app.get("/healthz")
    def healthz() -> dict:
        """Liveness probe."""
        return {"status": "ok"}

    @app.post("/")
    async def jsonrpc(request: Request) -> JSONResponse:
        """Dispatch one JSON-RPC 2.0 request (A2A methods)."""
        try:
            body = await request.json()
        except ValueError:
            return _jsonrpc_response(None, error=JsonRpcError(JSONRPC_PARSE_ERROR, "parse error").as_dict())
        request_id = body.get("id")
        method = body.get("method")
        params = body.get("params") or {}
        try:
            if not isinstance(method, str):
                raise JsonRpcError(JSONRPC_INVALID_REQUEST, "missing method")
            if method == "message/send":
                result = _handle_message_send(params)
            elif method == "tasks/get":
                result = _handle_tasks_get(params)
            else:
                raise JsonRpcError(JSONRPC_METHOD_NOT_FOUND, f"method {method!r} not found")
        except JsonRpcError as exc:
            return _jsonrpc_response(request_id, error=exc.as_dict())
        return _jsonrpc_response(request_id, result=result)

    return app


def _jsonrpc_response(request_id, result=None, error=None) -> JSONResponse:
    payload = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    return JSONResponse(payload)


def main() -> None:
    """Serve the A2A endpoint (uvicorn)."""
    import uvicorn

    host = os.environ.get("EDS_A2A_HOST", "127.0.0.1")
    port = int(os.environ.get("EDS_A2A_PORT", "8080"))
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
