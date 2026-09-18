import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.staff import Staff, StaffAvailability
from app.services.scheduling import SchedulingError, SlotUnavailableError, ensure_aware


async def list_staff_bookings(
    db: AsyncSession,
    *,
    staff_id: uuid.UUID,
    day: date,
) -> list[Booking]:
    day_start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    rows = await db.execute(
        select(Booking)
        .where(
            Booking.staff_id == staff_id,
            Booking.start_time < day_end,
            Booking.end_time > day_start,
        )
        .order_by(Booking.start_time)
    )
    return list(rows.scalars())


async def create_staff_block(
    db: AsyncSession,
    *,
    staff_id: uuid.UUID,
    start_time: datetime,
    end_time: datetime,
    note: str | None = None,
) -> StaffAvailability:
    start = ensure_aware(start_time)
    end = ensure_aware(end_time)
    if end <= start:
        raise SchedulingError("Block end_time must be after start_time")

    staff = await db.get(Staff, staff_id)
    if staff is None or not staff.is_active:
        raise SlotUnavailableError("Staff member not found")

    block = StaffAvailability(
        staff_id=staff_id,
        start_time=start,
        end_time=end,
        is_available=False,
        note=note,
    )
    db.add(block)
    await db.flush()
    await db.refresh(block)
    return block


async def delete_staff_block(
    db: AsyncSession,
    *,
    staff_id: uuid.UUID,
    block_id: uuid.UUID,
) -> None:
    block = await db.get(StaffAvailability, block_id)
    if block is None or block.staff_id != staff_id or block.is_available:
        raise SlotUnavailableError("Staff block not found")
    await db.delete(block)
