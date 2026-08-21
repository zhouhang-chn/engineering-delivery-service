"""Delivery Control tools: Work Order CRUD and lifecycle.

get_work_order / update_work_order / get_current_state /
mark_complete / mark_failed backed by the durable `WorkOrderState` in
PostgreSQL. Deterministic only — no policy decisions about what should
happen next (that belongs to the Supervisor).

TODO(M2): implement against real DB sessions and append audit events.
"""


def get_work_order(work_order_id: str):
    raise NotImplementedError


def update_work_order(work_order_id: str, **fields):
    raise NotImplementedError


def get_current_state(work_order_id: str):
    """Snapshot the Supervisor re-reads each turn instead of chat memory."""
    raise NotImplementedError


def mark_complete(work_order_id: str, summary: str):
    raise NotImplementedError


def mark_failed(work_order_id: str, reason: str):
    raise NotImplementedError
