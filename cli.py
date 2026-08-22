"""`eds` — the EDS command line: the reference external caller.

Four commands over the A2A protocol only — serve, submit, status
(--watch), open. This module never imports EDS internals except to
start the server (`serve`); using the CLI is itself a contract test of
the endpoint.

Usage:
  uv run eds serve [--host 127.0.0.1] [--port 8080]
  uv run eds submit "Add a GET /hello endpoint returning {'hello': 'world'}"
  uv run eds status wo-<id> --watch
  uv run eds open wo-<id>
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import webbrowser

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
EXIT_COMPLETED = 0
EXIT_FAILED = 1
EXIT_RUNNING = 2
TERMINAL_STATES = ("completed", "failed", "canceled")


def base_url(args) -> str:
    """Resolve the endpoint URL: flag > EDS_A2A_URL > default."""
    return getattr(args, "url", None) or os.environ.get("EDS_A2A_URL") or DEFAULT_BASE_URL


def _http_client(url: str) -> httpx.Client:
    """One HTTP client for the command (tests inject a fake transport)."""
    return httpx.Client(base_url=url, timeout=60.0)


class A2AClient:
    """The only A2A protocol surface the CLI touches."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def send_requirement(self, text: str) -> dict:
        """message/send: requirement text in, task out."""
        return self._rpc(
            "message/send",
            {
                "message": {
                    "messageId": f"eds-cli-{int(time.time() * 1000)}",
                    "role": "user",
                    "parts": [{"kind": "text", "text": text}],
                }
            },
        )

    def get_task(self, task_id: str) -> dict:
        """tasks/get: one task snapshot."""
        return self._rpc("tasks/get", {"id": task_id})

    def _rpc(self, method: str, params: dict) -> dict:
        response = self._client.post("/", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        body = response.json()
        if "error" in body:
            raise A2AError(body["error"].get("message", "A2A error"), body["error"].get("code"))
        return body["result"]


class A2AError(Exception):
    """One A2A / JSON-RPC error surfaced to the user."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


def _artifact_text(task: dict, name: str) -> str | None:
    for artifact in task.get("artifacts", []):
        if artifact.get("name") == name:
            parts = artifact.get("parts", [])
            if parts:
                return parts[0].get("text")
    return None


def render_task(task: dict) -> str:
    """Pretty-print one task: state, reason, artifacts."""
    status = task.get("status", {})
    lines = [f"task {task.get('id', '?')}  {status.get('state', '?')}"]
    message = status.get("message") or {}
    for part in message.get("parts", []):
        if part.get("text"):
            lines.append(f"  reason: {part['text']}")
    for artifact in task.get("artifacts", []):
        parts = artifact.get("parts", [])
        text = parts[0].get("text", "") if parts else ""
        lines.append(f"  {artifact.get('name', 'artifact')}: {text}")
    return "\n".join(lines)


def exit_code_for(state: str) -> int:
    """Exit codes for scripting: 0 completed, 1 failed, 2 still running."""
    if state == "completed":
        return EXIT_COMPLETED
    if state in ("failed", "canceled"):
        return EXIT_FAILED
    return EXIT_RUNNING


def cmd_serve(args) -> int:
    """Start EDS: the A2A endpoint on uvicorn."""
    import uvicorn

    from a2a_api.server import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)
    return EXIT_COMPLETED


def cmd_submit(args) -> int:
    """Submit a requirement as an A2A task; print the task id + state."""
    client = A2AClient(_http_client(base_url(args)))
    try:
        task = client.send_requirement(args.requirement)
    except A2AError as exc:
        print(f"error: {exc}")
        return EXIT_FAILED
    print(render_task(task))
    print(f"watch with: eds status {task['id']} --watch")
    return exit_code_for(task["status"]["state"])


def cmd_status(args) -> int:
    """Show a task; with --watch, poll until a terminal state."""
    client = A2AClient(_http_client(base_url(args)))
    while True:
        try:
            task = client.get_task(args.task_id)
        except A2AError as exc:
            print(f"error: {exc}")
            return EXIT_FAILED
        state = task["status"]["state"]
        if not args.watch or state in TERMINAL_STATES:
            print(render_task(task))
            return exit_code_for(state)
        if args.watch:
            print(f"[{time.strftime('%H:%M:%S')}] {state} ...", flush=True)
        time.sleep(args.interval)


def cmd_open(args) -> int:
    """Open the delivered /docs (Swagger UI) in the browser."""
    client = A2AClient(_http_client(base_url(args)))
    try:
        task = client.get_task(args.task_id)
    except A2AError as exc:
        print(f"error: {exc}")
        return EXIT_FAILED
    docs_url = _artifact_text(task, "docs_url")
    if not docs_url:
        print(
            f"no docs_url artifact on task {args.task_id} "
            f"(state: {task['status']['state']})"
        )
        return EXIT_FAILED
    print(docs_url)
    webbrowser.open(docs_url)
    return EXIT_COMPLETED


def build_parser() -> argparse.ArgumentParser:
    """The eds argument parser."""
    parser = argparse.ArgumentParser(
        prog="eds", description="Engineering Delivery Service CLI (A2A caller)."
    )
    parser.add_argument("--url", default=None, help="EDS A2A endpoint URL")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="start the EDS A2A endpoint")
    serve.add_argument("--host", default=os.environ.get("EDS_A2A_HOST", "127.0.0.1"))
    serve.add_argument("--port", type=int, default=int(os.environ.get("EDS_A2A_PORT", "8080")))

    submit = sub.add_parser("submit", help="submit a requirement as an A2A task")
    submit.add_argument("requirement")

    status = sub.add_parser("status", help="show a task; --watch polls to terminal")
    status.add_argument("task_id")
    status.add_argument("--watch", action="store_true", help="poll until terminal")
    status.add_argument("--interval", type=float, default=2.0, help="poll seconds")

    open_cmd = sub.add_parser("open", help="open the delivered /docs in a browser")
    open_cmd.add_argument("task_id")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint; returns the scripting exit code."""
    args = build_parser().parse_args(argv)
    handlers = {
        "serve": cmd_serve,
        "submit": cmd_submit,
        "status": cmd_status,
        "open": cmd_open,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
