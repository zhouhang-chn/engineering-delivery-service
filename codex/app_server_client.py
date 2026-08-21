"""Codex App Server client.

The bidirectional control interface to a Codex runtime: start/resume
threads, start turns, answer clarifications, approve/reject, steer,
interrupt — and stream turn status, messages, command executions, file
changes, questions and completion events.

See architecture doc section 9.
"""


class CodexAppServerClient:
    """Thin client over one Codex App Server's thread/turn API."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def start_turn(self, thread_id: str, prompt: str):
        """Kick off a turn on a thread; return its turn handle."""
        raise NotImplementedError

    def get_thread_events(self, thread_id: str):
        """Return the event stream (status, messages, approvals) for a thread."""
        raise NotImplementedError
