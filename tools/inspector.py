"""Delivery Control tools: inspector control.

Launch independent inspection of a candidate commit and read the verdict
(ACCEPT / REJECT), verified/failed criteria, evidence, gaps and risk.
Inspector never modifies the candidate. The independent Inspector
runtime arrives in v0.3 (M3); until then these reads report the
durable inspector fields (typically not provisioned).
"""

from __future__ import annotations

from control.state import session_scope
from db.models import WorkOrder


def get_inspector_status(work_order_id: str) -> dict:
    """Return Inspector runtime status, verdict and findings."""
    with session_scope() as session:
        work_order = session.get(WorkOrder, work_order_id)
        if work_order is None:
            return {"work_order_id": work_order_id, "status": "unknown"}
        return {
            "work_order_id": work_order_id,
            "status": work_order.inspector_status,
            "runtime_id": work_order.inspector_runtime_id,
            "thread_id": work_order.inspector_thread_id,
            "verdict": work_order.inspector_verdict,
            "findings": work_order.findings,
        }
