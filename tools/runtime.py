"""Delivery Control tools: runtime lifecycle.

create_worker_runtime / create_inspector_runtime / destroy_runtime.
Idempotent where possible; sandbox operations are wrapped in a bounded
RetryPolicy (operational retries only).
"""

from __future__ import annotations

from control.policy import RetryPolicy
from control.state import append_event, require_work_order, session_scope
from db.models import WorkOrder

ROLES = ("worker", "inspector")


def create_worker_runtime(work_order_id: str, *, base_dir=None) -> dict:
    """Provision the Worker runtime (sandbox; Codex thread starts later)."""
    return _create_role_runtime(work_order_id, "worker", base_dir=base_dir)


def create_inspector_runtime(work_order_id: str, *, base_dir=None) -> dict:
    """Provision the Inspector runtime (clean sandbox for later turns)."""
    return _create_role_runtime(work_order_id, "inspector", base_dir=base_dir)


def _create_role_runtime(work_order_id: str, role: str, *, base_dir) -> dict:
    """Create the role's sandbox and record it on the Work Order."""
    from sandbox import manager

    with session_scope() as session:
        work_order = require_work_order(session, work_order_id)
        runtime_id = getattr(work_order, f"{role}_runtime_id")
        if runtime_id:
            # idempotent re-issue: the runtime is already provisioned
            return {
                "work_order_id": work_order_id,
                "role": role,
                "runtime_id": runtime_id,
                "sandbox_path": str(manager.sandbox_path(runtime_id, base_dir)),
                f"{role}_status": getattr(work_order, f"{role}_status"),
            }
        sandbox = RetryPolicy().run(
            lambda: manager.create_sandbox(work_order_id, role, base_dir=base_dir),
            retry_on=OSError,
        )
        setattr(work_order, f"{role}_runtime_id", sandbox.sandbox_id)
        setattr(work_order, f"{role}_status", "starting")
        append_event(
            session,
            work_order_id,
            f"runtime.{role}_created",
            {"runtime_id": sandbox.sandbox_id, "sandbox_path": str(sandbox.path)},
        )
        session.flush()
        return {
            "work_order_id": work_order_id,
            "role": role,
            "runtime_id": sandbox.sandbox_id,
            "sandbox_path": str(sandbox.path),
            f"{role}_status": "starting",
        }


def destroy_runtime(runtime_id: str, *, base_dir=None) -> dict:
    """Tear down a runtime and release its sandbox (idempotent)."""
    from sandbox import manager

    work_order_id, _, role = runtime_id.partition("--")
    RetryPolicy().run(
        lambda: manager.destroy_sandbox(runtime_id, base_dir=base_dir),
        retry_on=OSError,
    )
    with session_scope() as session:
        work_order = session.get(WorkOrder, work_order_id)
        if work_order is not None and getattr(work_order, f"{role}_runtime_id", None) == runtime_id:
            setattr(work_order, f"{role}_status", "destroyed")
            append_event(session, work_order_id, "runtime.destroyed", {"runtime_id": runtime_id})
            session.flush()
    return {"runtime_id": runtime_id, "destroyed": True}
