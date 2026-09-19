"""configure services that block other services

Revision ID: 20260918_0004
Revises: 20260918_0003
Create Date: 2026-09-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260918_0004"
down_revision = "20260918_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service",
        sa.Column("blocks_other_services", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.execute("UPDATE service SET blocks_other_services = true WHERE lower(name) = 'massage'")


def downgrade() -> None:
    op.drop_column("service", "blocks_other_services")