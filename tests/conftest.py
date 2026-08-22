"""Shared pytest fixtures for the EDS test suite."""

import pytest

from tests.helpers.db import (  # noqa: F401
    db_engine,
    db_session_factory,
    db_url,
    durable_db,
)


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    """Keep the suite independent of any developer `.env`.

    Entrypoints now bootstrap their environment from `.env` (see
    `control.env`); tests that exercise them must not pick up whatever
    real values the developer keeps locally. Wiring tests re-patch
    `control.env.load_env` themselves and win over this no-op.
    """
    monkeypatch.setattr("control.env.load_env", lambda *args, **kwargs: False)
