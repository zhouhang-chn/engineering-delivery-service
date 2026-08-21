"""Delivery Control tools: worker control.

Start / resume / steer / answer clarifications on the Worker Codex
runtime, and read its candidate commit + engineering summary.
"""


def get_worker_status(work_order_id: str):
    """Return Worker runtime status, thread id and latest candidate state."""
    raise NotImplementedError
