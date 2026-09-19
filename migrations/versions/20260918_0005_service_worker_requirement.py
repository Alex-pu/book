"""track services that consume attendant capacity

Revision ID: 20260918_0005
Revises: 20260918_0004
Create Date: 2026-09-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260918_0005"
down_revision = "20260918_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service",
        sa.Column("requires_worker", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.execute(
        "UPDATE service SET requires_worker = "
        "(capacity_mode = 'worker' OR blocks_other_services)"
    )


def downgrade() -> None:
    op.drop_column("service", "requires_worker")