"""Live test (marked 'codex'): one real Codex App Server turn.

Run explicitly: uv run pytest -m codex

Validates the client binding end to end: initialize, thread/start with a
workspace cwd, turn/start, event stream, terminal turn status, and the
workspace side effect (file creation). Skips when the Codex account has
no remaining quota (the turn then completes with usageLimitExceeded).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from codex.app_server_client import CodexAppServerClient

pytestmark = pytest.mark.codex

WORKSPACE_PROMPT = (
    "Create a file named eds-live-marker.txt in the current directory "
    "containing the single line 'codex-live-ok'. Then reply: done."
)


def _wait_terminal(client: CodexAppServerClient, thread_id: str, timeout_s: float = 300.0):
    """Poll events until the turn completes; return the terminal turn dict."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        for event in client.poll_events(thread_id, block=True, timeout=2.0):
            if event.method == "turn/completed":
                return event.params.get("turn", {})
            if event.method == "error":
                message = (event.params.get("error") or {}).get("message", "")
                if not event.params.get("willRetry", False) and "usage limit" in message.lower():
                    pytest.skip(f"codex account usage-limited: {message}")
    pytest.fail("codex turn did not reach a terminal status in time")


def test_one_real_codex_turn_creates_file(tmp_path: Path) -> None:
    with CodexAppServerClient() as client:
        thread_id = client.start_thread(
            cwd=str(tmp_path),
            approval_policy="never",
            config={
                "sandbox_mode": "workspace-write",
                "sandbox_workspace_write": {"network_access": False},
            },
        )
        client.start_turn(thread_id, WORKSPACE_PROMPT)
        turn = _wait_terminal(client, thread_id)

    assert turn.get("status") == "completed", turn
    marker = tmp_path / "eds-live-marker.txt"
    assert marker.read_text().strip() == "codex-live-ok"
