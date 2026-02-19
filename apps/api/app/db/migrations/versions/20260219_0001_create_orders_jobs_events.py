"""create orders, delivery_jobs, delivery_events

Revision ID: 20260219_0001
Revises:
Create Date: 2026-02-19 00:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260219_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

order_priority = sa.Enum("NORMAL", "URGENT", "MEDICAL", name="order_priority")
order_status = sa.Enum(
    "CREATED",
    "VALIDATED",
    "QUEUED",
    "ASSIGNED",
    "MISSION_SUBMITTED",
    "LAUNCHED",
    "ENROUTE",
    "ARRIVED",
    "DELIVERING",
    "DELIVERED",
    "CANCELED",
    "FAILED",
    "ABORTED",
    name="order_status",
)
delivery_job_status = sa.Enum(
    "PENDING", "ACTIVE", "COMPLETED", "FAILED", name="delivery_job_status"
)
proof_of_delivery_method = sa.Enum(
    "PHOTO",
    "OTP",
    "OPERATOR_CONFIRM",
    name="proof_of_delivery_method",
)

delivery_event_type = sa.Enum(
    "CREATED",
    "VALIDATED",
    "QUEUED",
    "ASSIGNED",
    "MISSION_SUBMITTED",
    "LAUNCHED",
    "ENROUTE",
    "ARRIVED",
    "DELIVERING",
    "DELIVERED",
    "CANCELED",
    "FAILED",
    "ABORTED",
    name="delivery_event_type",
)


def upgrade() -> None:
    bind = op.get_bind()
    order_priority.create(bind, checkfirst=True)
    order_status.create(bind, checkfirst=True)
    delivery_job_status.create(bind, checkfirst=True)
    delivery_event_type.create(bind, checkfirst=True)
    proof_of_delivery_method.create(bind, checkfirst=True)

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_tracking_id", sa.String(length=32), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("customer_phone", sa.String(length=50), nullable=True),
        sa.Column("pickup_lat", sa.Float(), nullable=False),
        sa.Column("pickup_lng", sa.Float(), nullable=False),
        sa.Column("dropoff_lat", sa.Float(), nullable=False),
        sa.Column("dropoff_lng", sa.Float(), nullable=False),
        sa.Column("dropoff_accuracy_m", sa.Float(), nullable=True),
        sa.Column("payload_weight_kg", sa.Float(), nullable=False),
        sa.Column("payload_type", sa.String(length=100), nullable=False),
        sa.Column("priority", order_priority, nullable=False),
        sa.Column("status", order_status, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_orders_public_tracking_id"),
        "orders",
        ["public_tracking_id"],
        unique=True,
    )

    op.create_table(
        "delivery_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_drone_id", sa.String(length=100), nullable=True),
        sa.Column("mission_intent_id", sa.String(length=100), nullable=True),
        sa.Column("eta_seconds", sa.Integer(), nullable=True),
        sa.Column("status", delivery_job_status, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_delivery_jobs_order_id"), "delivery_jobs", ["order_id"], unique=False)

    op.create_table(
        "delivery_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("type", delivery_event_type, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["delivery_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_delivery_events_job_id"), "delivery_events", ["job_id"], unique=False)
    op.create_index(
        op.f("ix_delivery_events_order_id"), "delivery_events", ["order_id"], unique=False
    )



    op.create_table(
        "proof_of_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("method", proof_of_delivery_method, nullable=False),
        sa.Column("photo_url", sa.String(length=1024), nullable=True),
        sa.Column("otp_hash", sa.String(length=255), nullable=True),
        sa.Column("confirmed_by", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_proof_of_deliveries_order_id"),
        "proof_of_deliveries",
        ["order_id"],
        unique=False,
    )

def downgrade() -> None:
    op.drop_index(op.f("ix_proof_of_deliveries_order_id"), table_name="proof_of_deliveries")
    op.drop_table("proof_of_deliveries")

    op.drop_index(op.f("ix_delivery_events_order_id"), table_name="delivery_events")
    op.drop_index(op.f("ix_delivery_events_job_id"), table_name="delivery_events")
    op.drop_table("delivery_events")

    op.drop_index(op.f("ix_delivery_jobs_order_id"), table_name="delivery_jobs")
    op.drop_table("delivery_jobs")

    op.drop_index(op.f("ix_orders_public_tracking_id"), table_name="orders")
    op.drop_table("orders")

    bind = op.get_bind()
    proof_of_delivery_method.drop(bind, checkfirst=True)
    delivery_event_type.drop(bind, checkfirst=True)
    delivery_job_status.drop(bind, checkfirst=True)
    order_status.drop(bind, checkfirst=True)
    order_priority.drop(bind, checkfirst=True)
