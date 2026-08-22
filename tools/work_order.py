"""Delivery Control tools: Work Order CRUD and lifecycle.

get_work_order / update_work_order / get_current_state /
mark_complete / mark_failed backed by the durable `WorkOrder` in
PostgreSQL. Deterministic only — no policy decisions about what should
happen next (that belongs to the Supervisor).

Every state-changing call appends one audit Event row in the same
transaction as the mutation (delivery-control design §3 "Audited").
"""

from __future__ import annotations

from control.state import append_event, iso, require_work_order, session_scope
from db.models import Event, Evidence, WorkOrder

TERMINAL_STATUSES = ("complete", "failed")
RECENT_EVENT_LIMIT = 8

WRITABLE_FIELDS = frozenset(
    {
        "project_id",
        "repository",
        "baseline_commit",
        "original_request",
        "confirmed_requirement",
        "acceptance_criteria",
        "worker_runtime_id",
        "worker_thread_id",
        "worker_status",
        "worker_summary",
        "worker_error",
        "candidate_commit",
        "inspector_runtime_id",
        "inspector_thread_id",
        "inspector_status",
        "inspector_verdict",
        "findings",
        "testing",
        "deployment_status",
        "deployment_id",
        "deployment_url",
        "docs_url",
        "deployment_health",
        "gaps",
        "artifacts",
        "overall_status",
    }
)


def work_order_to_dict(work_order: WorkOrder) -> dict:
    """Serialize one Work Order row into a JSON-safe plain dict."""
    return {
        "id": work_order.id,
        "project_id": work_order.project_id,
        "repository": work_order.repository,
        "baseline_commit": work_order.baseline_commit,
        "original_request": work_order.original_request,
        "confirmed_requirement": work_order.confirmed_requirement,
        "acceptance_criteria": work_order.acceptance_criteria,
        "worker_runtime_id": work_order.worker_runtime_id,
        "worker_thread_id": work_order.worker_thread_id,
        "worker_status": work_order.worker_status,
        "worker_summary": work_order.worker_summary,
        "worker_error": work_order.worker_error,
        "candidate_commit": work_order.candidate_commit,
        "inspector_runtime_id": work_order.inspector_runtime_id,
        "inspector_thread_id": work_order.inspector_thread_id,
        "inspector_status": work_order.inspector_status,
        "inspector_verdict": work_order.inspector_verdict,
        "findings": work_order.findings,
        "testing": work_order.testing,
        "deployment_status": work_order.deployment_status,
        "deployment_id": work_order.deployment_id,
        "deployment_url": work_order.deployment_url,
        "docs_url": work_order.docs_url,
        "deployment_health": work_order.deployment_health,
        "gaps": work_order.gaps,
        "artifacts": work_order.artifacts,
        "overall_status": work_order.overall_status,
        "created_at": iso(work_order.created_at),
        "updated_at": iso(work_order.updated_at),
    }


def get_work_order(work_order_id: str) -> dict:
    """Return the full persisted Work Order record."""
    with session_scope() as session:
        return work_order_to_dict(require_work_order(session, work_order_id))


def update_work_order(work_order_id: str, **fields) -> dict:
    """Persist field updates to the Work Order (upsert, idempotent, audited).

    The first call for an id creates the row (`work_order.created`);
    later calls merge fields (`work_order.updated`).
    """
    if not isinstance(work_order_id, str) or not work_order_id:
        raise ValueError("work_order_id must be a non-empty string")
    if "id" in fields:
        raise ValueError("cannot change id")
    unknown = set(fields) - WRITABLE_FIELDS
    if unknown:
        raise ValueError(f"unknown work order field(s): {sorted(unknown)}")

    with session_scope() as session:
        work_order = session.get(WorkOrder, work_order_id)
        created = work_order is None
        if created:
            work_order = WorkOrder(id=work_order_id)
            session.add(work_order)
            session.flush()  # the audit event below references this row
        for name, value in fields.items():
            setattr(work_order, name, value)
        append_event(
            session,
            work_order_id,
            "work_order.created" if created else "work_order.updated",
            {"fields": sorted(fields)},
        )
        session.flush()
        return work_order_to_dict(work_order)


def get_current_state(work_order_id: str) -> dict:
    """Return the state snapshot the Supervisor re-reads each turn.

    Durable state replaces the Supervisor's conversation memory:
    current status, worker/inspector status, deployment state, open
    gaps, and the tail of the audit log.
    """
    with session_scope() as session:
        work_order = require_work_order(session, work_order_id)
        event_count = (
            session.query(Event).filter_by(work_order_id=work_order_id).count()
        )
        evidence_count = (
            session.query(Evidence).filter_by(work_order_id=work_order_id).count()
        )
        recent_rows = (
            session.query(Event)
            .filter_by(work_order_id=work_order_id)
            .order_by(Event.id.desc())
            .limit(RECENT_EVENT_LIMIT)
            .all()
        )
        return {
            "work_order_id": work_order.id,
            "overall_status": work_order.overall_status,
            "requirement": {
                "original_request": work_order.original_request,
                "confirmed_requirement": work_order.confirmed_requirement,
                "acceptance_criteria": work_order.acceptance_criteria or [],
            },
            "worker": {
                "status": work_order.worker_status,
                "runtime_id": work_order.worker_runtime_id,
                "thread_id": work_order.worker_thread_id,
                "summary": work_order.worker_summary,
                "error": work_order.worker_error,
                "candidate_commit": work_order.candidate_commit,
            },
            "inspector": {
                "status": work_order.inspector_status,
                "runtime_id": work_order.inspector_runtime_id,
                "thread_id": work_order.inspector_thread_id,
                "verdict": work_order.inspector_verdict,
                "findings": work_order.findings,
            },
            "deployment": {
                "status": work_order.deployment_status,
                "id": work_order.deployment_id,
                "url": work_order.deployment_url,
                "docs_url": work_order.docs_url,
                "health": work_order.deployment_health,
            },
            "gaps": work_order.gaps or [],
            "artifacts": work_order.artifacts or [],
            "evidence_count": evidence_count,
            "event_count": event_count,
            "recent_events": [
                {"seq": row.id, "type": row.type, "created_at": iso(row.created_at)}
                for row in reversed(recent_rows)
            ],
        }


def mark_complete(work_order_id: str, summary: str) -> dict:
    """Terminal transition: all criteria verified and deployment live."""
    return _mark_terminal(
        work_order_id,
        status="complete",
        event_type="work_order.marked_complete",
        artifact={"type": "completion_summary", "summary": summary},
        event_payload={"summary": summary},
    )


def mark_failed(work_order_id: str, reason: str) -> dict:
    """Terminal transition: delivery cannot continue; persist the reason."""
    return _mark_terminal(
        work_order_id,
        status="failed",
        event_type="work_order.marked_failed",
        artifact={"type": "failure_reason", "reason": reason},
        event_payload={"reason": reason},
    )


def _mark_terminal(
    work_order_id: str,
    *,
    status: str,
    event_type: str,
    artifact: dict,
    event_payload: dict,
) -> dict:
    """Apply one terminal transition; re-issuing the same mark is a no-op."""
    with session_scope() as session:
        work_order = require_work_order(session, work_order_id)
        current = work_order.overall_status
        if current in TERMINAL_STATUSES:
            if current != status:
                raise ValueError(
                    f"work order is terminal ({current!r}); cannot mark {status!r}"
                )
            return work_order_to_dict(work_order)
        work_order.overall_status = status
        artifacts = list(work_order.artifacts or [])
        artifacts.append(artifact)
        work_order.artifacts = artifacts
        append_event(session, work_order_id, event_type, event_payload)
        session.flush()
        return work_order_to_dict(work_order)
