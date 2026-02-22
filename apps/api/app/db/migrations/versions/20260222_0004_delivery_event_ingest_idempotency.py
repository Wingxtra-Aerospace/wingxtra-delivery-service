"""add delivery event ingest idempotency columns

Revision ID: 20260222_0004
Revises: 20260222_0003
Create Date: 2026-02-22 17:30:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "20260222_0004"
down_revision = "20260222_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delivery_events", sa.Column("ingest_source", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "delivery_events", sa.Column("ingest_event_id", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "delivery_events", sa.Column("ingest_event_type", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "delivery_events",
        sa.Column("ingest_occurred_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_delivery_events_ingest_event_id",
        "delivery_events",
        ["order_id", "ingest_source", "ingest_event_id"],
    )
    op.create_unique_constraint(
        "uq_delivery_events_ingest_source_type_time",
        "delivery_events",
        ["order_id", "ingest_source", "ingest_event_type", "ingest_occurred_at"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_delivery_events_ingest_source_type_time", "delivery_events", type_="unique"
    )
    op.drop_constraint("uq_delivery_events_ingest_event_id", "delivery_events", type_="unique")
    op.drop_column("delivery_events", "ingest_occurred_at")
    op.drop_column("delivery_events", "ingest_event_type")
    op.drop_column("delivery_events", "ingest_event_id")
    op.drop_column("delivery_events", "ingest_source")
