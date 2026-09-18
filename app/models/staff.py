import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'masseuse'"))
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    availability: Mapped[list["StaffAvailability"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )
    bookings = relationship("Booking", back_populates="staff", foreign_keys="Booking.staff_id")
    checkins = relationship("Checkin", back_populates="checked_in_by_staff")
    services = relationship("Service", secondary="staff_service", back_populates="staff")


class StaffAvailability(Base):
    __tablename__ = "staff_availability"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_staff_availability_time_order"),
        Index("idx_staff_availability_staff_time", "staff_id", "start_time", "end_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    staff: Mapped[Staff] = relationship(back_populates="availability")
