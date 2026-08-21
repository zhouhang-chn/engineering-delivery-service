"""Delivery Control tools: evidence persistence.

record_evidence persists pytest results, inspection verdicts, deployment
checks and other verifiable artifacts attached to a Work Order
(doc section 3: "Evidence 持久化").
"""


def record_evidence(work_order_id: str, kind: str, payload: dict):
    raise NotImplementedError
