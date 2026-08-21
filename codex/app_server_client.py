"""Codex App Server client.

The bidirectional control interface to a Codex runtime: start/resume
threads, start turns, answer clarifications, approve/reject, steer,
interrupt — and stream turn status, messages, command executions, file
changes, questions and completion events.

See architecture doc section 9.
"""


class CodexAppServerClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def start_turn(self, thread_id: str, prompt: str):
        raise NotImplementedError

    def get_thread_events(self, thread_id: str):
        raise NotImplementedError
