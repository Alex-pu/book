import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Numeric, Table, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


staff_service = Table(
    "staff_service",
    Base.metadata,
    Column(
        "staff_id", UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "service_id",
        UUID(as_uuid=True),
        ForeignKey("service.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Service(Base):
    __tablename__ = "service"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    duration_min: Mapped[int] = mapped_column(nullable=False)
    price_kes: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    capacity_mode: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'worker'"))
    capacity_limit: Mapped[int] = mapped_column(nullable=False, server_default=text("1"))
    requires_worker: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    staff = relationship("Staff", secondary=staff_service, back_populates="services")
    bookings = relationship("Booking", back_populates="service")
    booking_items = relationship("BookingItem", back_populates="service")
    schedule_items = relationship("BookingScheduleItem", back_populates="service")
    capacity_windows = relationship(
        "ServiceCapacityWindow", back_populates="service", cascade="all, delete-orphan"
    )


class ServiceCapacityWindow(Base):
    __tablename__ = "service_capacity_window"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_service_capacity_window_time_order"),
        CheckConstraint("capacity >= 0", name="ck_service_capacity_window_capacity"),
        Index("idx_service_capacity_window_service_time", "service_id", "start_time", "end_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service.id", ondelete="CASCADE"), nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity: Mapped[int] = mapped_column(nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    service = relationship("Service", back_populates="capacity_windows")
