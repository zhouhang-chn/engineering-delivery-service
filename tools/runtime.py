"""Delivery Control tools: runtime lifecycle.

create_worker_runtime / create_inspector_runtime / destroy_runtime /
get_worker_status / get_inspector_status. Idempotent where possible.
"""


def create_worker_runtime(work_order_id: str):
    raise NotImplementedError


def create_inspector_runtime(work_order_id: str):
    raise NotImplementedError


def destroy_runtime(runtime_id: str):
    raise NotImplementedError
