"""A fake A2A server for CLI tests.

Implements just the wire surface the CLI speaks (JSON-RPC
``message/send`` / ``tasks/get`` + agent card) with a canned state
machine, so CLI tests exercise the real protocol path with no EDS
backend at all: a task is ``working`` for the first two ``tasks/get``
calls, then ``completed`` with artifacts — unless the requirement
contains the word "fail", in which case it ends ``failed``.
"""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class FakeA2ABackend:
    """Canned task state machine backing the fake endpoint."""

    def __init__(self, polls_before_terminal: int = 2) -> None:
        self.polls_before_terminal = polls_before_terminal
        self.tasks: dict[str, dict] = {}
        self.poll_counts: dict[str, int] = {}

    def submit(self, requirement: str) -> dict:
        task_id = f"wo-fake-{uuid.uuid4().hex[:8]}"
        task = {
            "id": task_id,
            "contextId": task_id,
            "kind": "task",
            "status": {"state": "working", "timestamp": _now()},
        }
        self.tasks[task_id] = task
        return task

    def get(self, task_id: str) -> dict | None:
        task = self.tasks.get(task_id)
        if task is None:
            return None
        if task["status"]["state"] in ("completed", "failed"):
            return task
        count = self.poll_counts.get(task_id, 0) + 1
        self.poll_counts[task_id] = count
        if count >= self.polls_before_terminal:
            if "fail" in task["requirement"]:
                task["status"] = {
                    "state": "failed",
                    "timestamp": _now(),
                    "message": {
                        "role": "agent",
                        "parts": [{"kind": "text", "text": "worker failed: quota exceeded"}],
                    },
                }
            else:
                task["status"] = {"state": "completed", "timestamp": _now()}
                task["artifacts"] = [
                    {"artifactId": "1", "name": "repository", "parts": [
                        {"kind": "text", "text": "/fake/repo.git@abc123def456"}]},
                    {"artifactId": "2", "name": "deployment_url", "parts": [
                        {"kind": "text", "text": "http://localhost:54321"}]},
                    {"artifactId": "3", "name": "docs_url", "parts": [
                        {"kind": "text", "text": "http://localhost:54321/docs"}]},
                    {"artifactId": "4", "name": "pytest_evidence", "parts": [
                        {"kind": "text", "text": "pytest: passed (3 passed)"}]},
                    {"artifactId": "5", "name": "delivery_summary", "parts": [
                        {"kind": "text", "text": "delivered the fake thing"}]},
                ]
        return task


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def create_fake_a2a_app(backend: FakeA2ABackend | None = None) -> FastAPI:
    """Build the fake A2A JSON-RPC app."""
    active = backend or FakeA2ABackend()
    app = FastAPI()

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.post("/")
    async def jsonrpc(request: Request) -> JSONResponse:
        body = await request.json()
        method = body.get("method")
        params = body.get("params") or {}
        if method == "message/send":
            parts = (params.get("message") or {}).get("parts", [])
            requirement = "\n".join(
                p.get("text", "") for p in parts if p.get("kind") == "text"
            ).strip()
            task = active.submit(requirement)
            task["requirement"] = requirement
            return JSONResponse({"jsonrpc": "2.0", "id": body.get("id"), "result": task})
        if method == "tasks/get":
            task = active.get(params.get("id", ""))
            if task is None:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": body.get("id"),
                        "error": {"code": -32001, "message": "task not found"},
                    }
                )
            return JSONResponse({"jsonrpc": "2.0", "id": body.get("id"), "result": task})
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {"code": -32601, "message": f"method {method!r} not found"},
            }
        )

    return app
