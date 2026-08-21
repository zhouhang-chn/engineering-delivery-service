"""SQLAlchemy models for durable Work Order state (PostgreSQL).

Covers the architecture doc section 12 state shape, plus the append-only
`events` audit log and `evidence` records that Delivery Control owns
(doc section 3). Alembic manages migrations under db/migrations/.
"""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return uuid.uuid4().hex


class WorkOrder(Base):
    __tablename__ = "work_orders"

    # identity
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(String(64))
    repository: Mapped[str | None] = mapped_column(String(512))
    baseline_commit: Mapped[str | None] = mapped_column(String(64))

    # requirement
    original_request: Mapped[str | None] = mapped_column(Text)
    confirmed_requirement: Mapped[str | None] = mapped_column(Text)
    acceptance_criteria: Mapped[list | None] = mapped_column(JSON)

    # worker
    worker_runtime_id: Mapped[str | None] = mapped_column(String(64))
    worker_thread_id: Mapped[str | None] = mapped_column(String(64))
    worker_status: Mapped[str | None] = mapped_column(String(32))
    candidate_commit: Mapped[str | None] = mapped_column(String(64))

    # inspector
    inspector_runtime_id: Mapped[str | None] = mapped_column(String(64))
    inspector_thread_id: Mapped[str | None] = mapped_column(String(64))
    inspector_status: Mapped[str | None] = mapped_column(String(32))
    inspector_verdict: Mapped[str | None] = mapped_column(String(16))
    findings: Mapped[list | None] = mapped_column(JSON)

    # testing: {"pytest": ..., "api_contract": ..., "acceptance": ...}
    testing: Mapped[dict | None] = mapped_column(JSON)

    # deployment
    deployment_status: Mapped[str | None] = mapped_column(String(32))
    deployment_id: Mapped[str | None] = mapped_column(String(64))
    deployment_url: Mapped[str | None] = mapped_column(String(512))
    docs_url: Mapped[str | None] = mapped_column(String(512))
    deployment_health: Mapped[str | None] = mapped_column(String(32))

    gaps: Mapped[list | None] = mapped_column(JSON)
    artifacts: Mapped[list | None] = mapped_column(JSON)

    overall_status: Mapped[str] = mapped_column(String(32), default="submitted")

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    work_order_id: Mapped[str] = mapped_column(ForeignKey("work_orders.id"), index=True)
    kind: Mapped[str] = mapped_column(String(64))  # pytest_run | inspection | deployment_check | ...
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    """Append-only audit log (doc section 3, wired into tools in M2)."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    work_order_id: Mapped[str] = mapped_column(ForeignKey("work_orders.id"), index=True)
    type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
