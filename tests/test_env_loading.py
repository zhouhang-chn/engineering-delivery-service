"""`.env` bootstrap: EDS loads its own configuration, model credentials included.

The service must run without externally exported variables — `GOOGLE_API_KEY`
for the ADK Supervisor model lands in gitignored `.env`, and every process
entrypoint loads it via `control.env.load_env`.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

from control.env import load_env


def test_load_env_populates_environ_from_file(tmp_path, monkeypatch):
    """.env values (e.g. GOOGLE_API_KEY) reach os.environ untouched."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("EDS_LLM_MODEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('GOOGLE_API_KEY=test-key-123\nEDS_LLM_MODEL="gemini-2.5-pro"\n')

    assert load_env(env_file) is True
    assert os.environ["GOOGLE_API_KEY"] == "test-key-123"
    assert os.environ["EDS_LLM_MODEL"] == "gemini-2.5-pro"


def test_exported_variables_win_over_dotenv(tmp_path, monkeypatch):
    """Real environment keeps precedence — the file only fills gaps."""
    monkeypatch.setenv("GOOGLE_API_KEY", "exported-key")
    env_file = tmp_path / ".env"
    env_file.write_text("GOOGLE_API_KEY=file-key\n")

    load_env(env_file)
    assert os.environ["GOOGLE_API_KEY"] == "exported-key"


def test_missing_dotenv_is_silent(tmp_path):
    """No .env anywhere must not raise — exported env still works."""
    assert load_env(tmp_path / "does-not-exist.env") is False


def test_cli_main_bootstraps_env(monkeypatch):
    """The `eds` CLI loads .env before dispatching any command."""
    calls: list[object] = []
    monkeypatch.setattr("control.env.load_env", lambda *a, **k: calls.append(a) or True)

    import cli

    monkeypatch.setattr(cli, "cmd_status", lambda args: 0)
    cli.main(["status", "wo-x"])
    assert calls, "cli.main must call control.env.load_env before handling a command"


def test_server_main_bootstraps_env(monkeypatch):
    """`python -m a2a_api.server` loads .env before serving."""
    calls: list[object] = []
    monkeypatch.setattr("control.env.load_env", lambda *a, **k: calls.append(a) or True)

    stub_uvicorn = types.ModuleType("uvicorn")
    stub_uvicorn.run = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "uvicorn", stub_uvicorn)

    from a2a_api import server

    server.main()
    assert calls, "a2a_api.server.main must call control.env.load_env before uvicorn.run"


def test_agent_runner_main_bootstraps_env(monkeypatch):
    """`python -m agent.runner` loads .env before creating the work order."""
    calls: list[object] = []
    monkeypatch.setattr("control.env.load_env", lambda *a, **k: calls.append(a) or True)

    from agent import runner

    class _FakeThread:
        def join(self) -> None:
            pass

    fake_result = types.SimpleNamespace(
        work_order_id="wo-test",
        worker={},
        deployment={},
        overall_status="complete",
        reason=None,
    )
    monkeypatch.setattr(
        runner, "start_supervised_delivery", lambda *a, **k: ("wo-test", _FakeThread())
    )
    monkeypatch.setattr(
        runner, "get_current_state", lambda work_order_id: {"event_count": 0}
    )
    monkeypatch.setattr(runner, "_result_from_state", lambda *a, **k: fake_result)
    assert runner.main(["add a hello endpoint"]) == 0
    assert calls, "agent.runner.main must call control.env.load_env first"


def test_env_example_carries_model_configuration():
    """The committed template must list the provider credentials the app loads."""
    text = (Path(__file__).resolve().parent.parent / ".env.example").read_text()
    assert "GOOGLE_API_KEY=" in text
    assert "EDS_LLM_MODEL=" in text
