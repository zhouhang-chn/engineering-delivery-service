"""Unit tests for sandbox/manager.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from sandbox import manager


def test_create_sandbox_makes_role_directory(tmp_path: Path) -> None:
    sandbox = manager.create_sandbox("wo-1", "worker", base_dir=tmp_path)
    assert sandbox.path == tmp_path / "wo-1" / "worker"
    assert sandbox.path.is_dir()
    assert sandbox.sandbox_id == "wo-1--worker"


def test_create_sandbox_is_idempotent(tmp_path: Path) -> None:
    first = manager.create_sandbox("wo-1", "worker", base_dir=tmp_path)
    second = manager.create_sandbox("wo-1", "worker", base_dir=tmp_path)
    assert first.path == second.path


def test_worker_and_inspector_sandboxes_are_isolated(tmp_path: Path) -> None:
    worker = manager.create_sandbox("wo-1", "worker", base_dir=tmp_path)
    inspector = manager.create_sandbox("wo-1", "inspector", base_dir=tmp_path)
    assert worker.path != inspector.path
    assert manager.ROLES == ("worker", "inspector")


def test_create_sandbox_rejects_unknown_role(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown sandbox role"):
        manager.create_sandbox("wo-1", "supervisor", base_dir=tmp_path)


def test_destroy_sandbox_removes_and_is_idempotent(tmp_path: Path) -> None:
    sandbox = manager.create_sandbox("wo-1", "worker", base_dir=tmp_path)
    (sandbox.path / "repo").mkdir()
    manager.destroy_sandbox(sandbox.sandbox_id, base_dir=tmp_path)
    assert not sandbox.path.exists()
    manager.destroy_sandbox(sandbox.sandbox_id, base_dir=tmp_path)


def test_work_dir_respects_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EDS_WORK_DIR", str(tmp_path / "custom"))
    assert manager.work_dir() == (tmp_path / "custom").resolve()
    monkeypatch.delenv("EDS_WORK_DIR")
    assert manager.work_dir() == Path(manager.DEFAULT_WORK_DIR).resolve()


def test_work_dir_returns_absolute_paths() -> None:
    assert manager.work_dir("relative/work").is_absolute()
