"""Unit tests for codex/worker_driver.py (registry, prompt, ScriptedWorker)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from codex import worker_driver
from codex.worker_driver import (
    InMemoryWorkerRegistry,
    ScriptedWorker,
    WorkerTask,
    build_worker_prompt,
    get_worker_status,
    run_worker_task,
)


def make_task(tmp_path: Path) -> WorkerTask:
    """A minimal worker task rooted in a temp workspace."""
    return WorkerTask(requirement="add a hello endpoint", workspace=tmp_path)


def test_registry_lifecycle() -> None:
    registry = InMemoryWorkerRegistry()
    registry.init("wo-1")
    assert registry.get("wo-1").status == "starting"

    registry.set_status("wo-1", "running")
    registry.add_event("wo-1", "command", {"command": "pytest"})
    registry.set_status("wo-1", "done", summary="all green")

    snapshot = registry.get("wo-1")
    assert snapshot.status == "done"
    assert snapshot.summary == "all green"
    assert snapshot.events[0].type == "command"
    assert registry.get("wo-1").events == snapshot.events


def test_registry_unknown_work_order() -> None:
    assert InMemoryWorkerRegistry().get("missing").status == "unknown"


def test_registry_rejects_unknown_status() -> None:
    registry = InMemoryWorkerRegistry()
    with pytest.raises(ValueError, match="unknown worker status"):
        registry.set_status("wo-1", "vibing")


def test_prompt_embeds_task_contract(tmp_path: Path) -> None:
    task = WorkerTask(
        requirement="add a hello endpoint",
        workspace=tmp_path,
        acceptance_criteria=("GET /hello returns 200",),
        test_command="uv run pytest -q",
    )
    prompt = build_worker_prompt(task)
    assert str(tmp_path) in prompt
    assert "add a hello endpoint" in prompt
    assert "GET /hello returns 200" in prompt
    assert "uv run pytest -q" in prompt


def test_scripted_worker_writes_files_and_finishes(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    registry = InMemoryWorkerRegistry()
    registry.init("wo-1")
    script = [
        {"action": "status", "status": "running"},
        {"action": "write_file", "path": "app/hello.py", "content": "X = 1\n"},
        {"action": "event", "type": "command", "payload": {"exit_code": 0}},
        {"action": "status", "status": "done", "summary": "added endpoint"},
    ]
    ScriptedWorker(script).execute("wo-1", task, registry)

    assert (tmp_path / "app" / "hello.py").read_text() == "X = 1\n"
    status = registry.get("wo-1")
    assert status.status == "done"
    assert status.summary == "added endpoint"
    assert [e.type for e in status.events] == ["file_change", "command"]


def test_scripted_worker_fail_step(tmp_path: Path) -> None:
    registry = InMemoryWorkerRegistry()
    registry.init("wo-1")
    script = [{"action": "fail", "error": "boom"}]
    ScriptedWorker(script).execute("wo-1", make_task(tmp_path), registry)
    status = registry.get("wo-1")
    assert status.status == "failed"
    assert status.error == "boom"


def test_scripted_worker_rejects_unknown_action(tmp_path: Path) -> None:
    registry = InMemoryWorkerRegistry()
    registry.init("wo-1")
    with pytest.raises(ValueError, match="unknown script action"):
        ScriptedWorker([{"action": "teleport"}]).execute(
            "wo-1", make_task(tmp_path), registry
        )


def test_run_worker_task_runs_in_background(tmp_path: Path) -> None:
    registry = InMemoryWorkerRegistry()
    script = [
        {"action": "write_file", "path": "done.marker", "content": "ok"},
        {"action": "sleep", "seconds": 0.05},
    ]
    handle = run_worker_task(
        "wo-bg",
        make_task(tmp_path),
        worker=ScriptedWorker(script),
        registry=registry,
    )
    assert handle == "wo-bg"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if registry.get("wo-bg").status in ("done", "failed"):
            break
        time.sleep(0.02)
    assert registry.get("wo-bg").status == "done"
    assert (tmp_path / "done.marker").exists()


def test_default_registry_is_durable(tmp_path: Path, durable_db) -> None:
    """The module default now routes through PostgreSQL (v0.1.2)."""
    from tools.work_order import get_work_order

    run_worker_task(
        "wo-default",
        make_task(tmp_path),
        worker=ScriptedWorker([{"action": "status", "status": "done"}]),
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if get_worker_status("wo-default").status == "done":
            break
        time.sleep(0.02)
    assert get_worker_status("wo-default").status == "done"
    assert get_work_order("wo-default")["worker_status"] == "done"


def test_map_item_shapes() -> None:
    mapped = worker_driver._map_item(
        {"type": "commandExecution", "command": "pytest", "status": "completed",
         "exitCode": 0}
    )
    assert mapped is not None
    assert mapped[0] == "command"
    assert mapped[1]["command"] == "pytest"
    assert mapped[1]["exit_code"] == 0

    assert worker_driver._map_item({"type": "webSearch", "query": "x"}) is None
