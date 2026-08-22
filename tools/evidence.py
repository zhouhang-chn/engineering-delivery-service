"""Delivery Control tools: evidence persistence.

record_evidence persists pytest results, inspection verdicts, deployment
checks and other verifiable artifacts attached to a Work Order
(doc section 3: "Evidence 持久化").
"""

from __future__ import annotations

from control.state import append_event, iso, require_work_order, session_scope
from db.models import Evidence


def record_evidence(work_order_id: str, kind: str, payload: dict) -> dict:
    """Persist one verifiable artifact (test run, verdict, health check)."""
    if not isinstance(kind, str):
        raise TypeError("kind must be a string")
    if not kind:
        raise ValueError("kind must be a non-empty string")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise TypeError("payload must be a JSON object (dict)")

    with session_scope() as session:
        require_work_order(session, work_order_id)
        row = Evidence(work_order_id=work_order_id, kind=kind, payload=payload)
        session.add(row)
        append_event(
            session,
            work_order_id,
            "evidence.recorded",
            {"kind": kind, "evidence_id": row.id},
        )
        session.flush()
        return {
            "id": row.id,
            "work_order_id": work_order_id,
            "kind": kind,
            "payload": payload,
            "created_at": iso(row.created_at),
        }
