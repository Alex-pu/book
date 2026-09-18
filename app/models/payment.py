import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


disbursement_payment = Table(
    "disbursement_payment",
    Base.metadata,
    Column(
        "disbursement_id",
        UUID(as_uuid=True),
        ForeignKey("disbursement.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "payment_id",
        UUID(as_uuid=True),
        ForeignKey("payment.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Payment(Base):
    __tablename__ = "payment"
    __table_args__ = (Index("idx_payment_booking", "booking_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("booking.id", ondelete="CASCADE"), nullable=False
    )
    checkout_request_id: Mapped[str | None] = mapped_column(Text, unique=True)
    mpesa_receipt_number: Mapped[str | None] = mapped_column(Text, unique=True)
    amount_kes: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    platform_fee_kes: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    net_to_forward_kes: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'initiated'"))
    raw_callback_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    booking = relationship("Booking", back_populates="payments")
    disbursements = relationship(
        "Disbursement", secondary=disbursement_payment, back_populates="payments"
    )


class Disbursement(Base):
    __tablename__ = "disbursement"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_amount_kes: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    payment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    daraja_conversation_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    raw_response: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    payments = relationship(
        "Payment", secondary=disbursement_payment, back_populates="disbursements"
    )
