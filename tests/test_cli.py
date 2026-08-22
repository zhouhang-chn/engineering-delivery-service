"""CLI tests (v0.1.5 core behavior): the `eds` command over a fake A2A server.

submit → status --watch → open against the canned wire surface; exit
codes 0 (completed) / 1 (failed) / 2 (still running). No EDS backend,
Codex or docker involved — using the CLI is itself the endpoint
contract test.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.helpers.fake_a2a import FakeA2ABackend, create_fake_a2a_app


@pytest.fixture
def fake_backend(monkeypatch):
    """Point the CLI at a fake A2A server via its injectable http client."""
    import cli

    backend = FakeA2ABackend(polls_before_terminal=2)
    app = create_fake_a2a_app(backend)
    test_client = TestClient(app, base_url="http://eds-fake")
    monkeypatch.setattr(cli, "_http_client", lambda base_url: test_client)
    return backend


def test_submit_prints_task_id_and_state(fake_backend, capsys) -> None:
    import cli

    code = cli.main(["submit", "Add a GET /hello endpoint"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_RUNNING
    assert "wo-fake-" in out
    assert "working" in out


def test_status_without_watch_prints_once_and_exits_running(
    fake_backend, capsys
) -> None:
    import cli

    submit_code = cli.main(["submit", "Add a GET /ping endpoint"])
    assert submit_code == cli.EXIT_RUNNING
    capsys.readouterr()
    code = cli.main(["status", _last_task_id(fake_backend)])
    out = capsys.readouterr().out
    assert code == cli.EXIT_RUNNING
    assert "working" in out


def test_status_watch_terminates_completed_with_artifacts(
    fake_backend, capsys
) -> None:
    import cli

    cli.main(["submit", "Add a GET /hello endpoint"])
    capsys.readouterr()
    code = cli.main(["status", _last_task_id(fake_backend), "--watch", "--interval", "0.01"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_COMPLETED
    assert "completed" in out
    for name in ("repository", "deployment_url", "docs_url", "pytest_evidence"):
        assert name in out
    assert "/fake/repo.git@abc123def456" in out
    assert "http://localhost:54321/docs" in out


def test_status_watch_failed_exits_one_with_reason(fake_backend, capsys) -> None:
    import cli

    cli.main(["submit", "make this delivery fail please"])
    capsys.readouterr()
    code = cli.main(["status", _last_task_id(fake_backend), "--watch", "--interval", "0.01"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_FAILED
    assert "failed" in out
    assert "quota exceeded" in out


def test_open_resolves_docs_url_and_browses(fake_backend, monkeypatch, capsys) -> None:
    import cli

    cli.main(["submit", "Add a GET /hello endpoint"])
    task_id = _last_task_id(fake_backend)
    fake_backend.get(task_id)  # advance to terminal
    capsys.readouterr()

    opened: list[str] = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: opened.append(url) or True)
    code = cli.main(["open", task_id])
    out = capsys.readouterr().out
    assert code == cli.EXIT_COMPLETED
    assert opened == ["http://localhost:54321/docs"]
    assert "http://localhost:54321/docs" in out


def test_open_without_docs_url_fails_cleanly(fake_backend, capsys) -> None:
    import cli

    cli.main(["submit", "Add a GET /hello endpoint"])
    task_id = _last_task_id(fake_backend)
    task = fake_backend.tasks[task_id]
    task["artifacts"] = []  # completed but no docs_url artifact
    fake_backend.poll_counts[task_id] = 99
    task["status"] = {"state": "completed"}
    capsys.readouterr()
    code = cli.main(["open", task_id])
    out = capsys.readouterr().out
    assert code == cli.EXIT_FAILED
    assert "docs_url" in out


def test_status_unknown_task_prints_error(fake_backend, capsys) -> None:
    import cli

    code = cli.main(["status", "wo-fake-nope"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_FAILED
    assert "not found" in out.lower()


def test_serve_flag_parsing() -> None:
    """serve parses host/port without starting a server."""
    import cli

    parser = cli.build_parser()
    args = parser.parse_args(["serve", "--host", "0.0.0.0", "--port", "9999"])
    assert args.command == "serve"
    assert args.host == "0.0.0.0"
    assert args.port == 9999


def _last_task_id(backend: FakeA2ABackend) -> str:
    assert backend.tasks, "submit a task first"
    return next(reversed(backend.tasks))
