"""Deterministic state primitives over PostgreSQL Work Order state.

Pure read/write helpers with no judgment about what should happen next —
that belongs to the Supervisor.
"""

from sqlalchemy import create_engine

from db.models import Base


def make_engine(database_url: str):
    return create_engine(database_url)


def init_schema(engine):
    Base.metadata.create_all(engine)
