"""Delivery Control tools: runtime lifecycle.

create_worker_runtime / create_inspector_runtime / destroy_runtime /
get_worker_status / get_inspector_status. Idempotent where possible.
"""


def create_worker_runtime(work_order_id: str):
    """Provision the Worker Codex runtime (sandbox + App Server thread)."""
    raise NotImplementedError


def create_inspector_runtime(work_order_id: str):
    """Provision the Inspector Codex runtime (clean sandbox + thread)."""
    raise NotImplementedError


def destroy_runtime(runtime_id: str):
    """Tear down a runtime and release its sandbox (idempotent)."""
    raise NotImplementedError
