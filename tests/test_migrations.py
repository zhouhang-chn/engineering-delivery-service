"""Alembic migration tests (v0.1.2 T2).

``upgrade head`` must produce exactly the tables the models declare
(guards drift between db/models.py and revision 0001), and ``downgrade
base`` must cleanly remove them.
"""

from __future__ import annotations

from pathlib import Path

from tests.helpers.db import make_test_engine, scratch_database_url, table_names

EXPECTED_TABLES = {"work_orders", "events", "evidence"}


def _alembic_config(url: str):
    from alembic.config import Config

    project_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_upgrade_head_creates_model_schema(tmp_path: Path) -> None:
    from alembic import command

    url = scratch_database_url(tmp_path)
    command.upgrade(_alembic_config(url), "head")

    engine = make_test_engine(url)
    try:
        assert table_names(engine) == EXPECTED_TABLES
        _assert_columns_match_models(engine)
    finally:
        engine.dispose()


def test_downgrade_base_removes_schema(tmp_path: Path) -> None:
    from alembic import command

    url = scratch_database_url(tmp_path)
    cfg = _alembic_config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = make_test_engine(url)
    try:
        assert table_names(engine) == set()
    finally:
        engine.dispose()


def _assert_columns_match_models(engine) -> None:
    from sqlalchemy import inspect

    from db.models import Base

    inspector = inspect(engine)
    for table in EXPECTED_TABLES:
        migrated = {c["name"] for c in inspector.get_columns(table)}
        modeled = set(Base.metadata.tables[table].columns.keys())
        assert migrated == modeled, (
            f"{table}: migration and models disagree "
            f"(only-in-migration={migrated - modeled}, only-in-models={modeled - migrated})"
        )
