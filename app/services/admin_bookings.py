import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingScheduleItem
from app.models.catalog import Service
from app.services.scheduling import (
    SchedulingError,
    SlotUnavailableError,
    ensure_aware,
    get_service_or_raise,
    now_utc,
    schedule_service_units,
)


async def reschedule_confirmed_booking(
    db: AsyncSession,
    *,
    booking: Booking,
    start_time: datetime,
) -> Booking:
    if booking.status != "confirmed":
        raise SlotUnavailableError("Only confirmed bookings can be rescheduled")

    start = ensure_aware(start_time)
    lines = [(item.service, item.quantity) for item in booking.items]
    if not lines:
        raise SchedulingError("Booking has no services to reschedule")

    for schedule_item in list(booking.schedule_items):
        await db.delete(schedule_item)
    await db.flush()

    schedules: list[BookingScheduleItem] = []
    cursor = start
    for service, quantity in lines:
        service_schedule = await schedule_service_units(
            db,
            service=service,
            quantity=quantity,
            start_time=cursor,
            at_time=now_utc() - timedelta(minutes=1),
            exclude_booking_id=booking.id,
        )
        schedules.extend(service_schedule)
        cursor = max(item.end_time for item in service_schedule)

    booking.schedule_items = schedules
    booking.start_time = start
    booking.end_time = max(item.end_time for item in schedules)
    booking.updated_at = now_utc()
    await db.flush()
    return booking