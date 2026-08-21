"""Delivery Control tools: Work Order CRUD.

get_work_order / update_work_order backed by the durable
`WorkOrderState` in PostgreSQL. Deterministic only — no policy decisions.
"""


def get_work_order(work_order_id: str):
    raise NotImplementedError


def update_work_order(work_order_id: str, **fields):
    raise NotImplementedError
