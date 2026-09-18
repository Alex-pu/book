import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Booking(Base):
    __tablename__ = "booking"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_booking_time_order"),
        CheckConstraint("party_size > 0", name="ck_booking_party_size_positive"),
        Index("idx_booking_staff_time", "staff_id", "start_time", "end_time"),
        Index("idx_booking_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service.id"), nullable=False
    )
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=True
    )
    created_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=True
    )
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)
    customer_phone: Mapped[str] = mapped_column(Text, nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'online'"))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending_payment'")
    )
    lock_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    service = relationship("Service", back_populates="bookings")
    staff = relationship("Staff", back_populates="bookings", foreign_keys=[staff_id])
    created_by_staff = relationship("Staff", foreign_keys=[created_by_staff_id])
    items = relationship("BookingItem", back_populates="booking", cascade="all, delete-orphan")
    schedule_items = relationship(
        "BookingScheduleItem", back_populates="booking", cascade="all, delete-orphan"
    )
    payments = relationship("Payment", back_populates="booking", cascade="all, delete-orphan")
    checkins = relationship("Checkin", back_populates="booking")
    notifications = relationship("NotificationLog", back_populates="booking")


class BookingItem(Base):
    __tablename__ = "booking_item"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_booking_item_quantity_positive"),
        Index("idx_booking_item_booking", "booking_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("booking.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_kes: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_total_kes: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    booking = relationship("Booking", back_populates="items")
    service = relationship("Service", back_populates="booking_items")


class BookingScheduleItem(Base):
    __tablename__ = "booking_schedule_item"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_booking_schedule_item_time_order"),
        CheckConstraint("units > 0", name="ck_booking_schedule_item_units_positive"),
        Index("idx_booking_schedule_item_service_time", "service_id", "start_time", "end_time"),
        Index("idx_booking_schedule_item_booking", "booking_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("booking.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service.id"), nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    booking = relationship("Booking", back_populates="schedule_items")
    service = relationship("Service", back_populates="schedule_items")
