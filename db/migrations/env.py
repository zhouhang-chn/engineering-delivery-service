"""Alembic migration environment for the EDS durable-state schema."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic import context
from sqlalchemy import engine_from_config, pool

from control.state import DEFAULT_DATABASE_URL
from db.models import Base

config = context.config

if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option(
        "sqlalchemy.url", os.environ.get("EDS_DATABASE_URL") or DEFAULT_DATABASE_URL
    )

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit migration SQL to stdout instead of executing it."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
