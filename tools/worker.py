"""Delivery Control tools: worker control.

Start / resume / steer / answer clarifications on the Worker Codex
runtime, and read its candidate commit + engineering summary. Status
facts live on the Work Order row; observed actions live in the audit
log under the ``worker.*`` type namespace.
"""

from __future__ import annotations

from control.state import session_scope
from db.models import Event, WorkOrder

WORKER_EVENT_LIMIT = 20


def get_worker_status(work_order_id: str) -> dict:
    """Return Worker runtime status, thread id and latest candidate state."""
    with session_scope() as session:
        work_order = session.get(WorkOrder, work_order_id)
        if work_order is None:
            return {"work_order_id": work_order_id, "status": "unknown"}
        rows = (
            session.query(Event)
            .filter(
                Event.work_order_id == work_order_id,
                Event.type.like("worker.%"),
                Event.type != "worker_status.changed",
            )
            .order_by(Event.id.desc())
            .limit(WORKER_EVENT_LIMIT)
            .all()
        )
        events = [
            {"type": row.type.removeprefix("worker."), "payload": row.payload, "seq": row.id}
            for row in reversed(rows)
        ]
        return {
            "work_order_id": work_order_id,
            "status": work_order.worker_status,
            "runtime_id": work_order.worker_runtime_id,
            "thread_id": work_order.worker_thread_id,
            "summary": work_order.worker_summary,
            "error": work_order.worker_error,
            "candidate_commit": work_order.candidate_commit,
            "events": events,
        }
