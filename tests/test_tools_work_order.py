"""Work-order tool unit tests (v0.1.2 T1): CRUD, snapshot, terminal marks.

Every test asserts both the returned dict shape and the audit trail —
a state-changing tool call without its Event row is a bug, not a style
issue (delivery-control design §3 "Audited").
"""

from __future__ import annotations

import pytest

from tests.helpers.db import event_types, new_id


def test_update_work_order_creates_row_with_created_event(durable_db) -> None:
    from tools.work_order import get_work_order, update_work_order

    wo = new_id()
    record = update_work_order(
        wo,
        original_request="add a hello endpoint",
        confirmed_requirement="add a hello endpoint",
        acceptance_criteria=["GET /hello returns 200"],
        overall_status="in_progress",
    )

    assert record["id"] == wo
    assert record["original_request"] == "add a hello endpoint"
    assert record["acceptance_criteria"] == ["GET /hello returns 200"]
    assert record["overall_status"] == "in_progress"

    persisted = get_work_order(wo)
    assert persisted["confirmed_requirement"] == "add a hello endpoint"
    assert event_types(durable_db, wo) == ["work_order.created"]


def test_update_work_order_merges_fields_and_audits_each_call(durable_db) -> None:
    from tools.work_order import update_work_order

    wo = new_id()
    update_work_order(wo, original_request="r1")
    record = update_work_order(wo, worker_status="running", candidate_commit="abc123")

    assert record["original_request"] == "r1"  # merge, not replace
    assert record["worker_status"] == "running"
    assert record["candidate_commit"] == "abc123"
    assert event_types(durable_db, wo) == ["work_order.created", "work_order.updated"]


def test_update_work_order_validates_fields(durable_db) -> None:
    from tools.work_order import update_work_order

    with pytest.raises(ValueError, match="unknown work order field"):
        update_work_order(new_id(), wing_status="flying")
    with pytest.raises(ValueError, match="cannot change id"):
        update_work_order(new_id(), id="wo-spoofed")
    with pytest.raises(LookupError, match="not found"):
        from tools.work_order import get_work_order

        get_work_order(new_id())


def test_get_current_state_snapshot_shape(durable_db) -> None:
    from tools.work_order import get_current_state, update_work_order

    wo = new_id()
    update_work_order(
        wo,
        original_request="req",
        acceptance_criteria=["c1"],
        repository="/tmp/repo.git",
        worker_status="done",
        worker_summary="built it",
        candidate_commit="deadbeef",
        deployment_status="deployed",
        deployment_url="http://localhost:9000",
        docs_url="http://localhost:9000/docs",
        deployment_health="healthy",
        gaps=[],
    )

    state = get_current_state(wo)
    assert state["work_order_id"] == wo
    assert state["overall_status"] == "submitted"  # default before any set
    assert state["requirement"] == {
        "original_request": "req",
        "confirmed_requirement": None,
        "acceptance_criteria": ["c1"],
    }
    assert state["worker"]["status"] == "done"
    assert state["worker"]["summary"] == "built it"
    assert state["worker"]["candidate_commit"] == "deadbeef"
    assert state["inspector"]["status"] is None
    assert state["deployment"] == {
        "status": "deployed",
        "id": None,
        "url": "http://localhost:9000",
        "docs_url": "http://localhost:9000/docs",
        "health": "healthy",
    }
    assert state["event_count"] == 1
    assert state["evidence_count"] == 0
    assert [e["type"] for e in state["recent_events"]] == ["work_order.created"]

    with pytest.raises(LookupError, match="not found"):
        get_current_state(new_id())


def test_mark_complete_persists_summary_and_is_idempotent(durable_db) -> None:
    from tools.work_order import mark_complete, update_work_order

    wo = new_id()
    update_work_order(wo, original_request="req")
    record = mark_complete(wo, "delivered GET /hello at /docs")

    assert record["overall_status"] == "complete"
    expected = {"type": "completion_summary", "summary": "delivered GET /hello at /docs"}
    assert expected in (record["artifacts"] or [])
    assert event_types(durable_db, wo) == [
        "work_order.created",
        "work_order.marked_complete",
    ]

    # idempotent re-issue: no duplicate event, no error
    again = mark_complete(wo, "delivered GET /hello at /docs")
    assert again["overall_status"] == "complete"
    assert event_types(durable_db, wo) == [
        "work_order.created",
        "work_order.marked_complete",
    ]


def test_mark_failed_persists_reason(durable_db) -> None:
    from tools.work_order import mark_failed, update_work_order

    wo = new_id()
    update_work_order(wo, original_request="req")
    record = mark_failed(wo, "pytest failed: 2 failed")

    assert record["overall_status"] == "failed"
    expected = {"type": "failure_reason", "reason": "pytest failed: 2 failed"}
    assert expected in (record["artifacts"] or [])
    assert "work_order.marked_failed" in event_types(durable_db, wo)


def test_terminal_states_reject_conflicting_marks(durable_db) -> None:
    from tools.work_order import mark_complete, mark_failed, update_work_order

    wo = new_id()
    update_work_order(wo, original_request="req")
    mark_failed(wo, "worker exploded")
    with pytest.raises(ValueError, match="terminal"):
        mark_complete(wo, "too late")

    other = new_id()
    update_work_order(other, original_request="req")
    mark_complete(other, "done")
    with pytest.raises(ValueError, match="terminal"):
        mark_failed(other, "reconsidered")
