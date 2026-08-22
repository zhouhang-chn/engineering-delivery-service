"""Worker driver: drives a Codex turn inside a writable sandbox.

The Worker designs APIs, edits code, adds tests, runs pytest, debugs and
commits the candidate. Its "done" only means the candidate is ready for
inspection, not that the Work Order is complete.

Status transitions: ``starting -> running -> waiting? -> done | failed``.
Status + events live in PostgreSQL (:class:`PostgresWorkerRegistry`);
:class:`InMemoryWorkerRegistry` is the hermetic test double with the
same interface.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Protocol

from codex.app_server_client import CodexAppServerClient, CodexAppServerError
from control.state import append_event, session_scope

WORKER_STATUSES = ("starting", "running", "waiting", "done", "failed")
DEFAULT_TEST_COMMAND = "uv run pytest -q"
COMMIT_CONVENTION = (
    "Commit all your changes on the current branch with a conventional-commit "
    "message: 'feat: <short summary>' (or 'fix:'/'test:' as appropriate)."
)


@dataclass(frozen=True)
class WorkerTask:
    """Input contract for one Worker turn (version design section 4)."""

    requirement: str
    workspace: Path
    acceptance_criteria: tuple[str, ...] = ()
    test_command: str = DEFAULT_TEST_COMMAND
    commit_convention: str = COMMIT_CONVENTION


@dataclass(frozen=True)
class WorkerEvent:
    """One observed worker action: command run, file change, message..."""

    type: str
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class WorkerStatus:
    """Snapshot of the worker runtime for one work order."""

    status: str
    events: tuple[WorkerEvent, ...] = ()
    summary: str | None = None
    candidate_commit: str | None = None
    error: str | None = None


class InMemoryWorkerRegistry:
    """Thread-safe in-memory status + event store (test double).

    The delivery path uses :class:`PostgresWorkerRegistry`; this twin
    keeps the exact same interface for hermetic unit tests.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, dict] = {}

    def init(self, work_order_id: str) -> None:
        """Register a work order in 'starting' state."""
        with self._lock:
            self._states[work_order_id] = {
                "status": "starting",
                "events": [],
                "summary": None,
                "candidate_commit": None,
                "error": None,
            }

    def set_status(self, work_order_id: str, status: str, **fields: object) -> None:
        """Transition the worker status, optionally setting extra fields."""
        if status not in WORKER_STATUSES:
            raise ValueError(f"unknown worker status {status!r}")
        with self._lock:
            state = self._states.setdefault(
                work_order_id,
                {"events": [], "summary": None, "candidate_commit": None, "error": None},
            )
            state["status"] = status
            for name, value in fields.items():
                if value is not None:
                    state[name] = value

    def add_event(self, work_order_id: str, type: str, payload: dict | None = None) -> None:
        """Append an observed worker event."""
        with self._lock:
            state = self._states.setdefault(
                work_order_id,
                {
                    "status": "starting",
                    "summary": None,
                    "candidate_commit": None,
                    "error": None,
                    "events": [],
                },
            )
            state["events"].append(WorkerEvent(type, payload or {}))

    def get(self, work_order_id: str) -> WorkerStatus:
        """Return an immutable status snapshot."""
        with self._lock:
            state = self._states.get(work_order_id)
            if state is None:
                return WorkerStatus(status="unknown")
            return WorkerStatus(
                status=state["status"],
                events=tuple(state["events"]),
                summary=state.get("summary"),
                candidate_commit=state.get("candidate_commit"),
                error=state.get("error"),
            )


class PostgresWorkerRegistry:
    """Durable registry: Work Order columns + ``worker.*`` audit rows.

    Same interface as :class:`InMemoryWorkerRegistry`, but every fact
    lands in PostgreSQL via ``control.state.session_scope`` (and thus
    whatever factory ``control.state.configure`` installed), so status
    survives process restarts. Status transitions audit as
    ``worker_status.changed`` (excluded from the events view, which by
    interface contract lists only observed worker actions).
    """

    FIELD_MAP: ClassVar[dict[str, str]] = {
        "summary": "worker_summary",
        "error": "worker_error",
        "candidate_commit": "candidate_commit",
        "thread_id": "worker_thread_id",
    }

    def _ensure_row(self, session, work_order_id: str):
        """Get the WorkOrder row, creating and flushing a stub when new."""
        from db.models import WorkOrder

        work_order = session.get(WorkOrder, work_order_id)
        if work_order is None:
            work_order = WorkOrder(id=work_order_id, worker_status="starting")
            session.add(work_order)
            session.flush()  # worker.* events reference this row
        return work_order

    def init(self, work_order_id: str) -> None:
        """Register a work order in 'starting' state."""
        with session_scope() as session:
            work_order = self._ensure_row(session, work_order_id)
            if work_order.worker_status is None:
                work_order.worker_status = "starting"
            session.flush()

    def set_status(self, work_order_id: str, status: str, **fields: object) -> None:
        """Transition the worker status, optionally setting extra fields."""
        if status not in WORKER_STATUSES:
            raise ValueError(f"unknown worker status {status!r}")
        unknown = set(fields) - set(self.FIELD_MAP)
        if unknown:
            raise ValueError(f"unknown worker field(s): {sorted(unknown)}")

        with session_scope() as session:
            work_order = self._ensure_row(session, work_order_id)
            work_order.worker_status = status
            for name, value in fields.items():
                if value is not None:
                    setattr(work_order, self.FIELD_MAP[name], value)
            append_event(
                session, work_order_id, "worker_status.changed", {"status": status}
            )
            session.flush()

    def add_event(self, work_order_id: str, type: str, payload: dict | None = None) -> None:
        """Append an observed worker event."""
        with session_scope() as session:
            self._ensure_row(session, work_order_id)
            append_event(session, work_order_id, f"worker.{type}", payload or {})

    def get(self, work_order_id: str) -> WorkerStatus:
        """Return an immutable status snapshot."""
        with session_scope() as session:
            from db.models import Event, WorkOrder

            work_order = session.get(WorkOrder, work_order_id)
            if work_order is None or work_order.worker_status is None:
                return WorkerStatus(status="unknown")
            rows = (
                session.query(Event)
                .filter(
                    Event.work_order_id == work_order_id,
                    Event.type.like("worker.%"),
                    Event.type != "worker_status.changed",
                )
                .order_by(Event.id.desc())
                .limit(50)
                .all()
            )
            events = tuple(
                WorkerEvent(row.type.removeprefix("worker."), row.payload or {})
                for row in reversed(rows)
            )
            return WorkerStatus(
                status=work_order.worker_status,
                events=events,
                summary=work_order.worker_summary,
                candidate_commit=work_order.candidate_commit,
                error=work_order.worker_error,
            )


def default_registry() -> PostgresWorkerRegistry:
    """The process default registry: durable, backed by control.state."""
    return PostgresWorkerRegistry()


AnyWorkerRegistry = InMemoryWorkerRegistry | PostgresWorkerRegistry


class WorkerRuntime(Protocol):
    """The interface both the Codex worker and ScriptedWorker implement."""

    def execute(self, work_order_id: str, task: WorkerTask, registry: AnyWorkerRegistry) -> None:
        """Run one worker turn to a terminal status, updating the registry."""


def build_worker_prompt(task: WorkerTask) -> str:
    """Render the Worker turn prompt from the task contract."""
    criteria = "\n".join(f"- {c}" for c in task.acceptance_criteria) or "- (none given)"
    return (
        "You are the Worker in an autonomous engineering delivery service.\n"
        "Implement the following requirement in the git repository at:\n"
        f"  {task.workspace}\n\n"
        "Requirement:\n"
        f"  {task.requirement}\n\n"
        "Acceptance criteria:\n"
        f"{criteria}\n\n"
        "Rules:\n"
        "1. Work only inside the repository directory above.\n"
        f"2. Run the test suite with: {task.test_command}\n"
        "3. Add or update tests so the acceptance criteria are covered.\n"
        f"4. {task.commit_convention}\n"
        "5. Do not ask questions; make reasonable engineering assumptions.\n\n"
        "When finished, reply with a short engineering summary: what you "
        "built, test results, and any remaining concerns."
    )


def _map_item(item: dict) -> tuple[str, dict] | None:
    """Map one app-server ThreadItem to a (event-type, payload) pair."""
    item_type = item.get("type")
    if item_type == "commandExecution":
        return "command", {
            "command": item.get("command"),
            "status": item.get("status"),
            "exit_code": (item.get("exitCode") or {}).get("code")
            if isinstance(item.get("exitCode"), dict)
            else item.get("exitCode"),
        }
    if item_type == "fileChange":
        return "file_change", {"changes": item.get("changes"), "status": item.get("status")}
    if item_type == "agentMessage":
        return "message", {"text": item.get("text")}
    if item_type == "error":
        return "error", {"message": item.get("message")}
    return None


class CodexWorkerDriver:
    """Worker runtime backed by a real Codex App Server turn."""

    def __init__(self, *, poll_timeout: float = 1.0):
        self.poll_timeout = poll_timeout

    def execute(self, work_order_id: str, task: WorkerTask, registry: AnyWorkerRegistry) -> None:
        """Run one Codex turn to completion, mirroring events into the registry."""
        registry.set_status(work_order_id, "running")
        config = {
            "sandbox_mode": "workspace-write",
            "sandbox_workspace_write": {"network_access": True},
        }
        try:
            with CodexAppServerClient() as client:
                thread_id = client.start_thread(cwd=str(task.workspace), config=config)
                registry.add_event(
                    work_order_id, "thread_started", {"thread_id": thread_id}
                )
                turn_id = client.start_turn(thread_id, build_worker_prompt(task))
                self._consume_events(
                    client, registry, work_order_id, thread_id, turn_id
                )
        except CodexAppServerError as exc:
            registry.set_status(work_order_id, "failed", error=str(exc))

    def _consume_events(
        self,
        client: CodexAppServerClient,
        registry: AnyWorkerRegistry,
        work_order_id: str,
        thread_id: str,
        turn_id: str,
    ) -> None:
        """Poll thread events until the turn reaches a terminal status."""
        last_message: str | None = None
        while True:
            events = client.poll_events(thread_id, block=True, timeout=self.poll_timeout)
            for event in events:
                if event.method == "turn/completed":
                    self._finish_turn(
                        registry, work_order_id, event.params.get("turn", {}), last_message
                    )
                    return
                if event.method == "error":
                    message = (event.params.get("error") or {}).get("message", "unknown error")
                    registry.add_event(work_order_id, "error", {"message": message})
                    if not event.params.get("willRetry", False):
                        registry.set_status(work_order_id, "failed", error=message)
                        return
                    continue
                if event.method in ("item/started", "item/completed"):
                    mapped = _map_item(event.params.get("item", {}))
                    if mapped:
                        event_type, payload = mapped
                        registry.add_event(work_order_id, event_type, payload)
                        if event_type == "message":
                            last_message = payload.get("text")

    def _finish_turn(
        self,
        registry: AnyWorkerRegistry,
        work_order_id: str,
        turn: dict,
        last_message: str | None,
    ) -> None:
        """Translate a terminal turn into a registry terminal status."""
        status = turn.get("status")
        if status == "completed":
            registry.set_status(work_order_id, "done", summary=last_message)
        elif status == "interrupted":
            registry.set_status(work_order_id, "failed", error="turn interrupted")
        else:
            error = (turn.get("error") or {}).get("message", f"turn {status}")
            registry.set_status(work_order_id, "failed", error=error)


class ScriptedWorker:
    """Test double / demo worker: replays a scripted sequence of actions.

    Script steps (list of dicts, or a path/JSON string):
      {"action": "status", "status": "...", "summary": "..."}
      {"action": "write_file", "path": "...", "content": "..."}
      {"action": "event", "type": "...", "payload": {...}}
      {"action": "sleep", "seconds": 0.1}
      {"action": "fail", "error": "..."}
    """

    def __init__(self, script: list[dict] | str | Path):
        if isinstance(script, (str, Path)):
            raw = Path(script).read_text()
            script = json.loads(raw)
        self.script = script

    def execute(self, work_order_id: str, task: WorkerTask, registry: AnyWorkerRegistry) -> None:
        """Replay the script against the task workspace and registry."""
        registry.set_status(work_order_id, "running")
        for step in self.script:
            action = step.get("action")
            if action == "status":
                registry.set_status(
                    work_order_id,
                    step["status"],
                    summary=step.get("summary"),
                    error=step.get("error"),
                )
            elif action == "write_file":
                target = task.workspace / step["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(step["content"])
                registry.add_event(
                    work_order_id, "file_change", {"path": step["path"]}
                )
            elif action == "event":
                registry.add_event(work_order_id, step["type"], step.get("payload", {}))
            elif action == "sleep":
                time.sleep(step.get("seconds", 0.1))
            elif action == "fail":
                registry.set_status(work_order_id, "failed", error=step.get("error"))
                return
            else:
                raise ValueError(f"unknown script action {action!r}")
        status = registry.get(work_order_id)
        if status.status not in ("done", "failed"):
            registry.set_status(work_order_id, "done", summary="scripted work complete")


def _crash_guarded_execute(
    worker: WorkerRuntime,
    work_order_id: str,
    task: WorkerTask,
    registry: AnyWorkerRegistry,
) -> None:
    """Run one worker turn; an unexpected crash becomes a durable failure.

    An exception escaping ``worker.execute`` used to kill the worker
    thread silently, leaving the status on ``running`` forever — the
    Supervisor would poll a dead worker with no way to detect it. The
    guard persists the crash so ``get_worker_status`` reports it.
    """
    try:
        worker.execute(work_order_id, task, registry)
    except Exception as exc:  # noqa: BLE001 - the guard itself must never raise
        error = f"{type(exc).__name__}: {exc}"
        registry.set_status(work_order_id, "failed", error=error)
        registry.add_event(work_order_id, "crash", {"error": error})


def run_worker_task(
    work_order_id: str,
    task: WorkerTask,
    *,
    worker: WorkerRuntime | None = None,
    registry: AnyWorkerRegistry | None = None,
) -> str:
    """Start one worker turn in the background; return the work order id.

    The handle is polled via :func:`get_worker_status`. Without an
    explicit registry the durable PostgreSQL registry is used.
    """
    active_registry = registry or default_registry()
    worker = worker or CodexWorkerDriver()
    active_registry.init(work_order_id)
    thread = threading.Thread(
        target=_crash_guarded_execute,
        args=(worker, work_order_id, task, active_registry),
        daemon=True,
        name=f"eds-worker-{work_order_id}",
    )
    thread.start()
    return work_order_id


def get_worker_status(
    work_order_id: str, registry: AnyWorkerRegistry | None = None
) -> WorkerStatus:
    """Read the current worker status snapshot for a work order."""
    return (registry or default_registry()).get(work_order_id)
