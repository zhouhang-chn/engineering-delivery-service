"""Deterministic state primitives over PostgreSQL Work Order state.

Pure read/write helpers with no judgment about what should happen next —
that belongs to the Supervisor.
"""

from sqlalchemy import create_engine

from db.models import Base


def make_engine(database_url: str):
    """Create a SQLAlchemy engine for the EDS database."""
    return create_engine(database_url)


def init_schema(engine):
    """Create all tables (development convenience; alembic owns migrations)."""
    Base.metadata.create_all(engine)


def append_event(session, work_order_id: str, type: str, payload: dict | None = None):
    """Append one row to the Work Order audit log.

    Deferred to v0.2 (M2): call from every Delivery Control tool.
    """
    from db.models import Event

    session.add(Event(work_order_id=work_order_id, type=type, payload=payload))
    session.commit()
