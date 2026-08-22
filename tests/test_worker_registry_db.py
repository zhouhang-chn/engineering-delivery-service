"""PostgreSQL-backed worker registry tests (v0.1.2 T6).

The registry keeps the in-memory interface (init/set_status/add_event/
get) but stores facts in ``work_orders`` + ``events`` rows, so a process
restart between steps shows identical status — the acceptance criterion
of this iteration.
"""

from __future__ import annotations

import pytest

from tests.helpers.db import new_id


def _make_registry():
    from codex.worker_driver import PostgresWorkerRegistry

    return PostgresWorkerRegistry()


def test_registry_lifecycle_is_durable(durable_db) -> None:
    from tools.work_order import get_work_order

    registry = _make_registry()
    wo = new_id()

    registry.init(wo)
    assert registry.get(wo).status == "starting"

    registry.set_status(wo, "running")
    registry.add_event(wo, "command", {"command": "pytest"})
    registry.set_status(wo, "done", summary="all green")

    snapshot = registry.get(wo)
    assert snapshot.status == "done"
    assert snapshot.summary == "all green"
    assert [e.type for e in snapshot.events] == ["command"]
    assert snapshot.events[0].payload == {"command": "pytest"}

    # the same facts are visible on the work order row itself
    record = get_work_order(wo)
    assert record["worker_status"] == "done"
    assert record["worker_summary"] == "all green"


def test_registry_unknown_work_order(durable_db) -> None:
    assert _make_registry().get(new_id("missing-")).status == "unknown"


def test_registry_rejects_unknown_status(durable_db) -> None:
    registry = _make_registry()
    with pytest.raises(ValueError, match="unknown worker status"):
        registry.set_status(new_id(), "vibing")


def test_registry_rejects_unknown_field(durable_db) -> None:
    registry = _make_registry()
    with pytest.raises(ValueError, match="unknown worker field"):
        registry.set_status(new_id(), "running", wing_span="wide")


def test_registry_maps_extra_fields_to_columns(durable_db) -> None:
    from tools.work_order import get_work_order

    registry = _make_registry()
    wo = new_id()
    registry.init(wo)
    registry.set_status(wo, "failed", error="boom", candidate_commit="abc", thread_id="t-1")

    snapshot = registry.get(wo)
    assert snapshot.error == "boom"
    assert snapshot.candidate_commit == "abc"

    record = get_work_order(wo)
    assert record["worker_error"] == "boom"
    assert record["worker_thread_id"] == "t-1"


def test_worker_events_survive_engine_restart(
    db_engine, db_session_factory, db_url
) -> None:
    """Restart-mid-flow: dispose the engine (simulated crash), re-read."""
    from sqlalchemy.orm import sessionmaker

    from codex.worker_driver import PostgresWorkerRegistry
    from control import state
    from tests.helpers.db import make_test_engine

    state.configure(db_session_factory)
    wo = new_id()
    registry = PostgresWorkerRegistry()
    registry.init(wo)
    registry.set_status(wo, "running")
    registry.add_event(wo, "file_change", {"path": "app/main.py"})
    registry.add_event(wo, "command", {"command": "pytest -q", "exit_code": 0})
    registry.set_status(wo, "waiting", summary="halfway through")
    before = registry.get(wo)
    state.reset()

    db_engine.dispose()  # simulated crash: connection pool gone

    fresh_engine = make_test_engine(db_url)
    fresh_factory = sessionmaker(bind=fresh_engine, expire_on_commit=False)
    state.configure(fresh_factory)
    try:
        after = PostgresWorkerRegistry().get(wo)
    finally:
        state.reset()
        fresh_engine.dispose()

    assert after.status == before.status == "waiting"
    assert after.summary == before.summary == "halfway through"
    assert [e.type for e in after.events] == [e.type for e in before.events]
    assert [e.payload for e in after.events] == [e.payload for e in before.events]
