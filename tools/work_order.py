"""Delivery Control tools: Work Order CRUD and lifecycle.

get_work_order / update_work_order / get_current_state /
mark_complete / mark_failed backed by the durable `WorkOrderState` in
PostgreSQL. Deterministic only — no policy decisions about what should
happen next (that belongs to the Supervisor).

Deferred to v0.2 (M2): implement against real DB sessions and append
audit events via control.state.append_event.
"""


def get_work_order(work_order_id: str):
    """Return the full persisted Work Order record."""
    raise NotImplementedError


def update_work_order(work_order_id: str, **fields):
    """Persist field updates to the Work Order (idempotent, audited)."""
    raise NotImplementedError


def get_current_state(work_order_id: str):
    """Return the state snapshot the Supervisor re-reads each turn.

    Durable state replaces the Supervisor's conversation memory:
    current phase, worker/inspector status, open gaps, deployment state.
    """
    raise NotImplementedError


def mark_complete(work_order_id: str, summary: str):
    """Terminal transition: all criteria verified and deployment live."""
    raise NotImplementedError


def mark_failed(work_order_id: str, reason: str):
    """Terminal transition: delivery cannot continue; persist the reason."""
    raise NotImplementedError
