"""SQLAlchemy models for durable Work Order state (PostgreSQL).

Minimal M1/M2 draft per architecture doc section 12. Evolves with each
milestone; alembic manages migrations under db/migrations/.
"""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return uuid.uuid4().hex


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(String(64))
    repository: Mapped[str | None] = mapped_column(String(512))
    baseline_commit: Mapped[str | None] = mapped_column(String(64))

    original_request: Mapped[str | None] = mapped_column(String(8192))
    confirmed_requirement: Mapped[str | None] = mapped_column(String(8192))
    acceptance_criteria: Mapped[list | None] = mapped_column(JSON)

    worker_thread_id: Mapped[str | None] = mapped_column(String(64))
    candidate_commit: Mapped[str | None] = mapped_column(String(64))

    inspector_verdict: Mapped[str | None] = mapped_column(String(16))
    findings: Mapped[list | None] = mapped_column(JSON)

    deployment_status: Mapped[str | None] = mapped_column(String(32))
    deployment_url: Mapped[str | None] = mapped_column(String(512))
    docs_url: Mapped[str | None] = mapped_column(String(512))

    artifacts: Mapped[list | None] = mapped_column(JSON)
    overall_status: Mapped[str] = mapped_column(String(32), default="submitted")

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
