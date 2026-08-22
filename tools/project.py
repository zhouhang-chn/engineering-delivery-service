"""Delivery Control tools: project resolution.

resolve_project maps a Work Order to a registered Git repository and
baseline commit. MVP M1 uses a single fixed FastAPI template repository.
"""

from __future__ import annotations

from control.state import require_work_order, session_scope


def resolve_project(work_order_id: str) -> dict:
    """Return the repository URL and baseline commit for a Work Order."""
    with session_scope() as session:
        work_order = require_work_order(session, work_order_id)
        return {
            "work_order_id": work_order.id,
            "repository": work_order.repository,
            "baseline_commit": work_order.baseline_commit,
        }
