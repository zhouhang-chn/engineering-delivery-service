"""Database helpers for durable-state tests.

Contract tests prefer the real PostgreSQL engine (the docker compose
`postgres` service on localhost:5432); when it is not reachable the
helper falls back to a SQLite file so fast unit runs work without
Docker. Both paths exercise the same SQL layer — only the engine
differs. Set ``EDS_TEST_DATABASE_URL`` to force a specific target.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, event

POSTGRES_ADMIN_URL = "postgresql://eds:eds@localhost:5432/eds"
TEST_DATABASE = "eds_test"
MIGRATION_DATABASE = "eds_test_alembic"


def new_id(prefix: str = "wo-") -> str:
    """A unique, filesystem-safe work order id for one test."""
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def _postgres_reachable() -> bool:
    """Probe the compose postgres once with a short timeout."""
    try:
        import psycopg

        with psycopg.connect(POSTGRES_ADMIN_URL, connect_timeout=2, autocommit=True):
            return True
    except Exception:  # noqa: BLE001 - any failure means "not reachable"
        return False


def _recreate_database(name: str) -> None:
    """Drop and re-create a scratch database on the compose postgres."""
    import psycopg

    with psycopg.connect(POSTGRES_ADMIN_URL, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {name}")


def database_url(tmp_dir) -> str:
    """Resolve the test database URL: env override > postgres > sqlite file."""
    env_url = os.environ.get("EDS_TEST_DATABASE_URL")
    if env_url:
        return env_url
    if _postgres_reachable():
        _recreate_database(TEST_DATABASE)
        return f"postgresql+psycopg://eds:eds@localhost:5432/{TEST_DATABASE}"
    return f"sqlite:///{tmp_dir / 'eds-test.db'}"


def scratch_database_url(tmp_dir) -> str:
    """A private empty database for migration tests (never re-used)."""
    if not os.environ.get("EDS_TEST_DATABASE_URL") and _postgres_reachable():
        _recreate_database(MIGRATION_DATABASE)
        return f"postgresql+psycopg://eds:eds@localhost:5432/{MIGRATION_DATABASE}"
    return f"sqlite:///{tmp_dir / 'eds-scratch.db'}"


def make_test_engine(url: str):
    """Create an engine, hardening SQLite for concurrent test access."""
    engine = create_engine(url)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def table_names(engine) -> set[str]:
    """All non-alembic table names present on an engine."""
    from sqlalchemy import inspect

    return {
        name
        for name in inspect(engine).get_table_names()
        if not name.startswith("alembic_")
    }


def event_types(session_factory, work_order_id: str) -> list[str]:
    """Audit event types for a work order, in append order."""
    from db.models import Event

    with session_factory() as session:
        rows = session.query(Event).filter_by(work_order_id=work_order_id).order_by(Event.id)
        return [row.type for row in rows]


def evidence_kinds(session_factory, work_order_id: str) -> list[str]:
    """Evidence kinds recorded for a work order, in insert order."""
    from db.models import Evidence

    with session_factory() as session:
        rows = session.query(Evidence).filter_by(work_order_id=work_order_id)
        return [row.kind for row in rows]


@pytest.fixture(scope="session")
def db_url(tmp_path_factory) -> str:
    """One database per test session (tests use unique work order ids)."""
    return database_url(tmp_path_factory.mktemp("eds-db"))


@pytest.fixture(scope="session")
def db_engine(db_url):
    """The shared test engine with the schema initialized."""
    from control import state

    engine = make_test_engine(db_url)
    state.init_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def db_session_factory(db_engine):
    """A sessionmaker over the shared test database."""
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=db_engine, expire_on_commit=False)


@pytest.fixture
def durable_db(db_session_factory):
    """Configure the tools' default session factory; restore afterwards."""
    from control import state

    state.configure(db_session_factory)
    try:
        yield db_session_factory
    finally:
        state.reset()
