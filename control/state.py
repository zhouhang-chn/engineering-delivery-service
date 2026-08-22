"""Deterministic state primitives over PostgreSQL Work Order state.

Pure read/write helpers with no judgment about what should happen next —
that belongs to the Supervisor. Tools open one short ``session_scope``
per call: the mutation and its audit event commit atomically.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base

DEFAULT_DATABASE_URL = "postgresql+psycopg://eds:eds@localhost:5432/eds"

_engine = None
_session_factory = None


def database_url() -> str:
    """Resolve the EDS database URL (EDS_DATABASE_URL > compose default)."""
    return os.environ.get("EDS_DATABASE_URL") or DEFAULT_DATABASE_URL


def make_engine(database_url: str):
    """Create a SQLAlchemy engine for the EDS database."""
    return create_engine(database_url)


def init_schema(engine):
    """Create all tables (development convenience; alembic owns migrations)."""
    Base.metadata.create_all(engine)


def default_engine():
    """The process-wide engine for the EDS database (created lazily)."""
    global _engine
    if _engine is None:
        _engine = make_engine(database_url())
    return _engine


def configure(session_factory) -> None:
    """Point the default session factory at one engine (tests, runner)."""
    global _session_factory
    _session_factory = session_factory


def reset() -> None:
    """Drop an explicit configuration; fall back to the default engine."""
    global _session_factory
    _session_factory = None


def default_session_factory():
    """The sessionmaker every tool uses, unless configured otherwise."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=default_engine(), expire_on_commit=False)
    return _session_factory


@contextmanager
def session_scope():
    """One short transaction: commit on success, rollback on error."""
    session = default_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def require_work_order(session, work_order_id: str):
    """Fetch a WorkOrder row or raise LookupError (shared tool guard)."""
    from db.models import WorkOrder

    work_order = session.get(WorkOrder, work_order_id)
    if work_order is None:
        raise LookupError(f"work order {work_order_id!r} not found")
    return work_order


def iso(value) -> str | None:
    """Serialize a datetime column value to an ISO-8601 string."""
    return value.isoformat() if value is not None else None


def append_event(session, work_order_id: str, type: str, payload: dict | None = None):
    """Queue one audit Event row; the caller's commit persists it atomically."""
    from db.models import Event

    event = Event(work_order_id=work_order_id, type=type, payload=payload)
    session.add(event)
    session.flush()
    return event
