"""tighten idempotency uniqueness to scope + key

Revision ID: 20260222_0003
Revises: 20260221_0002
Create Date: 2026-02-22 00:03:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260222_0003"
down_revision: str | None = "20260221_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_idem_scope_key", "idempotency_records", type_="unique")
    op.create_unique_constraint(
        "uq_idem_scope_key",
        "idempotency_records",
        ["route", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_idem_scope_key", "idempotency_records", type_="unique")
    op.create_unique_constraint(
        "uq_idem_scope_key",
        "idempotency_records",
        ["user_id", "route", "idempotency_key"],
    )
