import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.checkin import Checkin
from app.services.scheduling import SlotUnavailableError, now_utc


async def create_checkin(
    db: AsyncSession,
    *,
    checked_in_by: uuid.UUID,
    booking_id: uuid.UUID | None = None,
    customer_name: str | None = None,
) -> Checkin:
    if booking_id is None and not customer_name:
        raise SlotUnavailableError("booking_id or customer_name is required")

    resolved_customer_name = customer_name
    if booking_id is not None:
        booking = await db.get(Booking, booking_id)
        if booking is None:
            raise SlotUnavailableError("Booking not found")
        if booking.status != "confirmed":
            raise SlotUnavailableError("Only confirmed bookings can be checked in")
        booking.status = "checked_in"
        booking.updated_at = now_utc()
        resolved_customer_name = booking.customer_name

    checkin = Checkin(
        booking_id=booking_id,
        customer_name=resolved_customer_name,
        checked_in_by=checked_in_by,
    )
    db.add(checkin)
    await db.flush()
    await db.refresh(checkin)
    return checkin


async def checkout(db: AsyncSession, checkin_id: uuid.UUID) -> Checkin:
    checkin = await db.get(Checkin, checkin_id)
    if checkin is None:
        raise SlotUnavailableError("Check-in not found")
    if checkin.checked_out_at is not None:
        return checkin

    checkin.checked_out_at = now_utc()
    if checkin.booking_id is not None:
        booking = await db.get(Booking, checkin.booking_id)
        if booking is not None and booking.status == "checked_in":
            booking.status = "completed"
            booking.updated_at = now_utc()

    await db.flush()
    await db.refresh(checkin)
    return checkin


async def open_checkins(db: AsyncSession) -> list[Checkin]:
    rows = await db.execute(
        select(Checkin).where(Checkin.checked_out_at.is_(None)).order_by(Checkin.checked_in_at)
    )
    return list(rows.scalars())


async def current_presence_count(db: AsyncSession) -> int:
    count = await db.scalar(
        select(func.count()).select_from(Checkin).where(Checkin.checked_out_at.is_(None))
    )
    return int(count or 0)
