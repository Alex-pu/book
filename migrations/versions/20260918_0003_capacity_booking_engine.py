"""capacity booking engine

Revision ID: 20260918_0003
Revises: 20260918_0002
Create Date: 2026-09-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260918_0003"
down_revision = "20260918_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service",
        sa.Column("capacity_mode", sa.Text(), nullable=False, server_default=sa.text("'worker'")),
    )
    op.add_column(
        "service",
        sa.Column("capacity_limit", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )

    op.add_column("booking", sa.Column("created_by_staff_id", postgresql.UUID(as_uuid=True)))
    op.add_column(
        "booking",
        sa.Column("party_size", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "booking",
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'online'")),
    )
    op.alter_column("booking", "staff_id", nullable=True)
    op.create_foreign_key(
        "fk_booking_created_by_staff_id_staff",
        "booking",
        "staff",
        ["created_by_staff_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_booking_party_size_positive",
        "booking",
        "party_size > 0",
    )

    op.create_table(
        "service_capacity_window",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("end_time > start_time", name="ck_service_capacity_window_time_order"),
        sa.CheckConstraint("capacity >= 0", name="ck_service_capacity_window_capacity"),
    )
    op.create_index(
        "idx_service_capacity_window_service_time",
        "service_capacity_window",
        ["service_id", "start_time", "end_time"],
    )

    op.create_table(
        "booking_item",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("booking.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_kes", sa.Numeric(10, 2), nullable=False),
        sa.Column("line_total_kes", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("quantity > 0", name="ck_booking_item_quantity_positive"),
    )
    op.create_index("idx_booking_item_booking", "booking_item", ["booking_id"])

    op.create_table(
        "booking_schedule_item",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("booking.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service.id"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("end_time > start_time", name="ck_booking_schedule_item_time_order"),
        sa.CheckConstraint("units > 0", name="ck_booking_schedule_item_units_positive"),
    )
    op.create_index("idx_booking_schedule_item_booking", "booking_schedule_item", ["booking_id"])
    op.create_index(
        "idx_booking_schedule_item_service_time",
        "booking_schedule_item",
        ["service_id", "start_time", "end_time"],
    )

    op.execute(
        """
        INSERT INTO booking_item (booking_id, service_id, quantity, unit_price_kes, line_total_kes)
        SELECT booking.id, booking.service_id, 1, service.price_kes, service.price_kes
        FROM booking
        JOIN service ON service.id = booking.service_id
        WHERE NOT EXISTS (
            SELECT 1 FROM booking_item WHERE booking_item.booking_id = booking.id
        )
        """
    )
    op.execute(
        """
        INSERT INTO booking_schedule_item (booking_id, service_id, start_time, end_time, units)
        SELECT id, service_id, start_time, end_time, 1
        FROM booking
        WHERE NOT EXISTS (
            SELECT 1 FROM booking_schedule_item
            WHERE booking_schedule_item.booking_id = booking.id
        )
        """
    )


def downgrade() -> None:
    op.drop_index("idx_booking_schedule_item_service_time", table_name="booking_schedule_item")
    op.drop_index("idx_booking_schedule_item_booking", table_name="booking_schedule_item")
    op.drop_table("booking_schedule_item")
    op.drop_index("idx_booking_item_booking", table_name="booking_item")
    op.drop_table("booking_item")
    op.drop_index("idx_service_capacity_window_service_time", table_name="service_capacity_window")
    op.drop_table("service_capacity_window")
    op.drop_constraint("ck_booking_party_size_positive", "booking", type_="check")
    op.drop_constraint("fk_booking_created_by_staff_id_staff", "booking", type_="foreignkey")
    op.alter_column("booking", "staff_id", nullable=False)
    op.drop_column("booking", "source")
    op.drop_column("booking", "party_size")
    op.drop_column("booking", "created_by_staff_id")
    op.drop_column("service", "capacity_limit")
    op.drop_column("service", "capacity_mode")
