"""Codex App Server client.

The bidirectional control interface to a Codex runtime: start/resume
threads, start turns, answer clarifications, approve/reject — and stream
turn status, messages, command executions, file changes and completion
events.

Protocol (validated against codex-cli 0.146.0, see v0.1.1 implementation
notes): newline-delimited JSON-RPC 2.0 over the stdio of
``codex app-server``.

  initialize(clientInfo) -> session info
  thread/start {cwd, approvalPolicy, config} -> thread id
  turn/start {threadId, input: [{type: "text", text}]} -> turn id
  notifications: thread/status/changed, turn/started, item/started,
  item/completed, item/agentMessage/delta, error, turn/completed
  server->client requests: item/commandExecution/requestApproval,
  item/fileChange/requestApproval, item/tool/requestUserInput ...

The transport is isolated in this module; callers only see
:class:`AppServerEvent` objects and turn handles.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Self

DEFAULT_APP_SERVER_COMMAND = "codex app-server"
CLIENT_INFO = {"name": "eds", "title": "Engineering Delivery Service", "version": "0.1.0"}
TERMINAL_TURN_STATUSES = ("completed", "interrupted", "failed")


class CodexAppServerError(RuntimeError):
    """Raised when the App Server returns an error or dies."""


@dataclass(frozen=True)
class AppServerEvent:
    """One notification (or server request) observed on the wire."""

    method: str
    params: dict = field(default_factory=dict)

    @property
    def thread_id(self) -> str | None:
        """The thread this event belongs to, when scoped."""
        return self.params.get("threadId")


def _default_command() -> list[str]:
    """Resolve the app-server command: env override or the default."""
    raw = os.environ.get("EDS_CODEX_APP_SERVER_URL", DEFAULT_APP_SERVER_COMMAND)
    return shlex.split(raw)


class CodexAppServerClient:
    """Client over one ``codex app-server`` process (JSON-RPC over stdio).

    Events are buffered until drained via :meth:`poll_events`; approval
    requests are answered automatically by a pluggable reply policy
    (default: accept, matching the autonomous worker runtime).
    """

    def __init__(self, command: list[str] | str | None = None, *, cwd: str | None = None):
        if isinstance(command, str):
            command = shlex.split(command)
        self._command = command or _default_command()
        self._cwd = cwd
        self._proc: subprocess.Popen | None = None
        self._events: deque[AppServerEvent] = deque()
        self._lock = threading.Lock()
        self._new_events = threading.Condition(self._lock)
        self._responses: dict[int, dict] = {}
        self._reply_policy = self._accept_approvals
        self._next_id = 0
        self._write_lock = threading.Lock()
        self._stderr_tail: deque[str] = deque(maxlen=20)

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def start(self) -> None:
        """Spawn the app server, start pump threads and initialize."""
        self._proc = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=self._cwd,
        )
        threading.Thread(target=self._pump_stdout, daemon=True).start()
        threading.Thread(target=self._pump_stderr, daemon=True).start()
        self._request("initialize", {"clientInfo": CLIENT_INFO})

    def close(self) -> None:
        """Terminate the app server process (idempotent)."""
        proc, self._proc = self._proc, None
        if proc is None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    # -- control surface ----------------------------------------------------

    def set_reply_policy(self, policy) -> None:
        """Install a callback ``fn(method) -> result-dict`` for server requests."""
        self._reply_policy = policy

    def start_thread(
        self,
        cwd: str,
        *,
        approval_policy: str = "never",
        config: dict | None = None,
    ) -> str:
        """Start a conversation thread rooted at cwd; return the thread id."""
        params: dict = {
            "cwd": cwd,
            "approvalPolicy": approval_policy,
        }
        if config:
            params["config"] = config
        result = self._request("thread/start", params)
        return result["thread"]["id"]

    def start_turn(self, thread_id: str, prompt: str) -> str:
        """Send one user turn on the thread; return the turn id."""
        result = self._request(
            "turn/start",
            {"threadId": thread_id, "input": [{"type": "text", "text": prompt}]},
        )
        return result["turn"]["id"]

    def interrupt(self, thread_id: str) -> None:
        """Request interruption of the thread's active turn."""
        self._request("turn/interrupt", {"threadId": thread_id})

    def poll_events(
        self,
        thread_id: str | None = None,
        *,
        block: bool = False,
        timeout: float | None = None,
    ) -> list[AppServerEvent]:
        """Drain buffered events (optionally scoped to one thread).

        With ``block=True`` waits up to ``timeout`` seconds for at least
        one event. Drained events are removed from the buffer.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._new_events:
            while True:
                matching = [
                    ev
                    for ev in self._events
                    if thread_id is None or ev.thread_id in (thread_id, None)
                ]
                if matching:
                    for ev in matching:
                        self._events.remove(ev)
                    return matching
                if not block:
                    return []
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return []
                self._new_events.wait(remaining if remaining is not None else 0.5)

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _accept_approvals(method: str) -> dict:
        """Default reply policy: approve command/file-change approvals."""
        if "requestApproval" in method or method.endswith("Approval"):
            return {"decision": "accept"}
        return {"response": {}}

    def _send(self, message: dict) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise CodexAppServerError("app server is not running")
        with self._write_lock:
            self._proc.stdin.write(json.dumps(message) + "\n")
            self._proc.stdin.flush()

    def _request(self, method: str, params: dict, timeout: float = 60.0) -> dict:
        """Send a JSON-RPC request and wait for its response."""
        with self._lock:
            self._next_id += 1
            request_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        with self._new_events:
            while request_id not in self._responses:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise CodexAppServerError(f"timeout waiting for response to {method}")
                self._new_events.wait(min(remaining, 0.5))
            response = self._responses.pop(request_id)
        if "error" in response:
            raise CodexAppServerError(f"{method} failed: {response['error']}")
        return response.get("result", {})

    def _record_event(self, event: AppServerEvent) -> None:
        with self._new_events:
            self._events.append(event)
            self._new_events.notify_all()

    def _pump_stdout(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                self._stderr_tail.append(f"non-json stdout: {line[:200]}")
                continue
            if "method" in message and "id" in message:
                event = AppServerEvent(message["method"], message.get("params", {}))
                self._record_event(event)
                try:
                    reply = self._reply_policy(message["method"])
                except Exception as exc:  # noqa: BLE001 - policy is plugin code
                    self._stderr_tail.append(f"reply policy failed: {exc}")
                    reply = {"decision": "reject"} if "Approval" in message["method"] else {}
                self._send({"jsonrpc": "2.0", "id": message["id"], "result": reply})
            elif "method" in message:
                self._record_event(AppServerEvent(message["method"], message.get("params", {})))
            elif "id" in message:
                with self._new_events:
                    self._responses[message["id"]] = message
                    self._new_events.notify_all()
        # stdout closed: record an error event so pollers observe the shutdown
        self._record_event(
            AppServerEvent("error", {"error": {"message": "app server stdout closed"}})
        )

    def _pump_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        for line in self._proc.stderr:
            self._stderr_tail.append(line.rstrip()[:200])
