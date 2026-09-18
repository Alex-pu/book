"""add staff email

Revision ID: 20260918_0002
Revises: 20260918_0001
Create Date: 2026-09-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260918_0002"
down_revision = "20260918_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("staff", sa.Column("email", sa.Text(), nullable=True))
    op.create_index("uq_staff_email", "staff", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_staff_email", table_name="staff")
    op.drop_column("staff", "email")
