"""initial schema

Revision ID: 20260918_0001
Revises:
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260918_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "staff",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False, unique=True),
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'masseuse'")),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "service",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("price_kes", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "staff_availability",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("end_time > start_time", name="ck_staff_availability_time_order"),
    )
    op.create_index(
        "idx_staff_availability_staff_time",
        "staff_availability",
        ["staff_id", "start_time", "end_time"],
    )
    op.create_table(
        "staff_service",
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "booking",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service.id"), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("customer_name", sa.Text(), nullable=False),
        sa.Column("customer_phone", sa.Text(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending_payment'")),
        sa.Column("lock_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("end_time > start_time", name="ck_booking_time_order"),
    )
    op.create_index("idx_booking_staff_time", "booking", ["staff_id", "start_time", "end_time"])
    op.create_index("idx_booking_status", "booking", ["status"])
    op.execute(
        """
        ALTER TABLE booking ADD CONSTRAINT no_overlapping_bookings
        EXCLUDE USING gist (
            staff_id WITH =,
            tstzrange(start_time, end_time) WITH &&
        ) WHERE (status IN ('confirmed','checked_in'))
        """
    )
    op.create_table(
        "payment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("booking.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checkout_request_id", sa.Text(), unique=True),
        sa.Column("mpesa_receipt_number", sa.Text(), unique=True),
        sa.Column("amount_kes", sa.Numeric(10, 2), nullable=False),
        sa.Column("platform_fee_kes", sa.Numeric(10, 2), nullable=False),
        sa.Column("net_to_forward_kes", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'initiated'")),
        sa.Column("raw_callback_payload", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_payment_booking", "payment", ["booking_id"])
    op.create_table(
        "disbursement",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_amount_kes", sa.Numeric(10, 2), nullable=False),
        sa.Column("payment_count", sa.Integer(), nullable=False),
        sa.Column("daraja_conversation_id", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("raw_response", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "disbursement_payment",
        sa.Column("disbursement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("disbursement.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payment.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "checkin",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("booking.id")),
        sa.Column("customer_name", sa.Text()),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("checked_out_at", sa.DateTime(timezone=True)),
        sa.Column("checked_in_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
    )
    op.create_index(
        "idx_checkin_open",
        "checkin",
        ["checked_out_at"],
        postgresql_where=sa.text("checked_out_at IS NULL"),
    )
    op.create_table(
        "notification_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("booking.id")),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("provider_ref", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("notification_log")
    op.drop_index("idx_checkin_open", table_name="checkin")
    op.drop_table("checkin")
    op.drop_table("disbursement_payment")
    op.drop_table("disbursement")
    op.drop_index("idx_payment_booking", table_name="payment")
    op.drop_table("payment")
    op.execute("ALTER TABLE booking DROP CONSTRAINT IF EXISTS no_overlapping_bookings")
    op.drop_index("idx_booking_status", table_name="booking")
    op.drop_index("idx_booking_staff_time", table_name="booking")
    op.drop_table("booking")
    op.drop_table("staff_service")
    op.drop_index("idx_staff_availability_staff_time", table_name="staff_availability")
    op.drop_table("staff_availability")
    op.drop_table("service")
    op.drop_table("staff")
