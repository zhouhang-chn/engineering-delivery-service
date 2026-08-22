"""Initial EDS durable-state schema.

Revision ID: 0001
Revises:
Create Date: 2026-08-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create work_orders, evidence and events tables."""
    op.create_table(
        "work_orders",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("repository", sa.String(length=512), nullable=True),
        sa.Column("baseline_commit", sa.String(length=64), nullable=True),
        sa.Column("original_request", sa.Text(), nullable=True),
        sa.Column("confirmed_requirement", sa.Text(), nullable=True),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=True),
        sa.Column("worker_runtime_id", sa.String(length=64), nullable=True),
        sa.Column("worker_thread_id", sa.String(length=64), nullable=True),
        sa.Column("worker_status", sa.String(length=32), nullable=True),
        sa.Column("worker_summary", sa.Text(), nullable=True),
        sa.Column("worker_error", sa.Text(), nullable=True),
        sa.Column("candidate_commit", sa.String(length=64), nullable=True),
        sa.Column("inspector_runtime_id", sa.String(length=64), nullable=True),
        sa.Column("inspector_thread_id", sa.String(length=64), nullable=True),
        sa.Column("inspector_status", sa.String(length=32), nullable=True),
        sa.Column("inspector_verdict", sa.String(length=16), nullable=True),
        sa.Column("findings", sa.JSON(), nullable=True),
        sa.Column("testing", sa.JSON(), nullable=True),
        sa.Column("deployment_status", sa.String(length=32), nullable=True),
        sa.Column("deployment_id", sa.String(length=64), nullable=True),
        sa.Column("deployment_url", sa.String(length=512), nullable=True),
        sa.Column("docs_url", sa.String(length=512), nullable=True),
        sa.Column("deployment_health", sa.String(length=32), nullable=True),
        sa.Column("gaps", sa.JSON(), nullable=True),
        sa.Column("artifacts", sa.JSON(), nullable=True),
        sa.Column("overall_status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_table(
        "evidence",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "work_order_id",
            sa.String(length=32),
            sa.ForeignKey("work_orders.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_index("ix_evidence_work_order_id", "evidence", ["work_order_id"])
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "work_order_id",
            sa.String(length=32),
            sa.ForeignKey("work_orders.id"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_index("ix_events_work_order_id", "events", ["work_order_id"])


def downgrade() -> None:
    """Drop the initial schema."""
    op.drop_index("ix_events_work_order_id", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_evidence_work_order_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_table("work_orders")
