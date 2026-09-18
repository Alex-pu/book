import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, Table, Text, text
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
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    staff = relationship("Staff", secondary=staff_service, back_populates="services")
    bookings = relationship("Booking", back_populates="service")
