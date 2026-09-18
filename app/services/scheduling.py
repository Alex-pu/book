import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.catalog import Service, staff_service
from app.models.staff import Staff, StaffAvailability
from app.schemas.availability import AvailabilitySlot

ACTIVE_CONFLICT_STATUSES = ("confirmed", "checked_in")
PENDING_PAYMENT = "pending_payment"
SLOT_STEP_MINUTES = 30


class SchedulingError(ValueError):
    pass


class SlotUnavailableError(SchedulingError):
    pass


@dataclass(frozen=True)
class BookingWindow:
    start_time: datetime
    end_time: datetime


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SchedulingError("Datetime values must be timezone-aware")
    return value


def booking_window(start_time: datetime, duration_min: int) -> BookingWindow:
    if duration_min <= 0:
        raise SchedulingError("Service duration must be positive")
    start = ensure_aware(start_time)
    return BookingWindow(start_time=start, end_time=start + timedelta(minutes=duration_min))


def windows_overlap(
    start_time: datetime,
    end_time: datetime,
    other_start_time: datetime,
    other_end_time: datetime,
) -> bool:
    return start_time < other_end_time and end_time > other_start_time


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iter_slot_starts(
    window_start: datetime,
    window_end: datetime,
    *,
    duration_min: int,
    step_min: int = SLOT_STEP_MINUTES,
) -> list[datetime]:
    if duration_min <= 0:
        raise SchedulingError("Service duration must be positive")
    if step_min <= 0:
        raise SchedulingError("Slot step must be positive")

    starts: list[datetime] = []
    cursor = ensure_aware(window_start)
    end = ensure_aware(window_end)
    duration = timedelta(minutes=duration_min)
    step = timedelta(minutes=step_min)

    while cursor + duration <= end:
        starts.append(cursor)
        cursor += step
    return starts


def conflicting_bookings_statement(
    staff_id: uuid.UUID,
    start_time: datetime,
    end_time: datetime,
    *,
    at_time: datetime | None = None,
    for_update: bool = True,
) -> Select[tuple[Booking]]:
    moment = at_time or now_utc()
    stmt = (
        select(Booking)
        .where(
            Booking.staff_id == staff_id,
            Booking.start_time < end_time,
            Booking.end_time > start_time,
            or_(
                Booking.status.in_(ACTIVE_CONFLICT_STATUSES),
                and_(
                    Booking.status == PENDING_PAYMENT,
                    Booking.lock_expires_at.is_not(None),
                    Booking.lock_expires_at > moment,
                ),
            ),
        )
        .order_by(Booking.start_time)
    )
    if for_update:
        stmt = stmt.with_for_update()
    return stmt


async def ensure_staff_can_perform_service(
    db: AsyncSession,
    *,
    staff_id: uuid.UUID,
    service_id: uuid.UUID,
) -> None:
    stmt = (
        select(Staff.id)
        .join(staff_service, staff_service.c.staff_id == Staff.id)
        .where(
            Staff.id == staff_id,
            Staff.is_active.is_(True),
            staff_service.c.service_id == service_id,
        )
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise SlotUnavailableError("Staff member is not available for this service")


async def ensure_staff_has_open_window(
    db: AsyncSession,
    *,
    staff_id: uuid.UUID,
    start_time: datetime,
    end_time: datetime,
) -> None:
    open_stmt = select(StaffAvailability.id).where(
        StaffAvailability.staff_id == staff_id,
        StaffAvailability.is_available.is_(True),
        StaffAvailability.start_time <= start_time,
        StaffAvailability.end_time >= end_time,
    )
    if (await db.execute(open_stmt)).scalar_one_or_none() is None:
        raise SlotUnavailableError("Requested time is outside staff availability")

    block_stmt = select(StaffAvailability.id).where(
        StaffAvailability.staff_id == staff_id,
        StaffAvailability.is_available.is_(False),
        StaffAvailability.start_time < end_time,
        StaffAvailability.end_time > start_time,
    )
    if (await db.execute(block_stmt)).first() is not None:
        raise SlotUnavailableError("Requested time overlaps a staff block")


async def ensure_slot_available(
    db: AsyncSession,
    *,
    staff_id: uuid.UUID,
    start_time: datetime,
    end_time: datetime,
    at_time: datetime | None = None,
) -> None:
    stmt = conflicting_bookings_statement(
        staff_id,
        start_time,
        end_time,
        at_time=at_time,
        for_update=True,
    )
    if (await db.execute(stmt)).scalars().first() is not None:
        raise SlotUnavailableError("Requested slot is already booked")


async def get_service_or_raise(db: AsyncSession, service_id: uuid.UUID) -> Service:
    service = await db.get(Service, service_id)
    if service is None or not service.is_active:
        raise SlotUnavailableError("Service is not available")
    return service


async def create_soft_locked_booking(
    db: AsyncSession,
    *,
    service_id: uuid.UUID,
    staff_id: uuid.UUID,
    start_time: datetime,
    customer_name: str,
    customer_phone: str,
    lock_minutes: int,
) -> Booking:
    if lock_minutes <= 0:
        raise SchedulingError("Booking lock duration must be positive")

    service = await get_service_or_raise(db, service_id)
    window = booking_window(start_time, service.duration_min)
    moment = now_utc()

    await ensure_staff_can_perform_service(db, staff_id=staff_id, service_id=service_id)
    await ensure_staff_has_open_window(
        db,
        staff_id=staff_id,
        start_time=window.start_time,
        end_time=window.end_time,
    )
    await ensure_slot_available(
        db,
        staff_id=staff_id,
        start_time=window.start_time,
        end_time=window.end_time,
        at_time=moment,
    )

    booking = Booking(
        service_id=service_id,
        staff_id=staff_id,
        customer_name=customer_name.strip(),
        customer_phone=customer_phone.strip(),
        start_time=window.start_time,
        end_time=window.end_time,
        status=PENDING_PAYMENT,
        lock_expires_at=moment + timedelta(minutes=lock_minutes),
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking)
    return booking


async def list_available_slots(
    db: AsyncSession,
    *,
    service_id: uuid.UUID,
    day: date,
) -> list[AvailabilitySlot]:
    service = await get_service_or_raise(db, service_id)
    day_start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    moment = now_utc()

    staff_rows = await db.execute(
        select(Staff.id, Staff.full_name)
        .join(staff_service, staff_service.c.staff_id == Staff.id)
        .where(
            Staff.is_active.is_(True),
            staff_service.c.service_id == service_id,
        )
        .order_by(Staff.full_name)
    )
    staff = staff_rows.all()
    if not staff:
        return []

    slots: list[AvailabilitySlot] = []
    duration = timedelta(minutes=service.duration_min)

    for staff_id, staff_name in staff:
        availability_rows = await db.execute(
            select(StaffAvailability)
            .where(
                StaffAvailability.staff_id == staff_id,
                StaffAvailability.start_time < day_end,
                StaffAvailability.end_time > day_start,
            )
            .order_by(StaffAvailability.start_time)
        )
        availability = list(availability_rows.scalars())
        open_windows = [row for row in availability if row.is_available]
        blocks = [row for row in availability if not row.is_available]

        booking_rows = await db.execute(
            conflicting_bookings_statement(
                staff_id,
                day_start,
                day_end,
                at_time=moment,
                for_update=False,
            )
        )
        conflicts = list(booking_rows.scalars())

        for open_window in open_windows:
            window_start = max(open_window.start_time, day_start)
            window_end = min(open_window.end_time, day_end)
            for slot_start in iter_slot_starts(
                window_start,
                window_end,
                duration_min=service.duration_min,
            ):
                slot_end = slot_start + duration
                blocked = any(
                    windows_overlap(slot_start, slot_end, block.start_time, block.end_time)
                    for block in blocks
                )
                booked = any(
                    windows_overlap(slot_start, slot_end, booking.start_time, booking.end_time)
                    for booking in conflicts
                )
                if not blocked and not booked and slot_start > moment:
                    slots.append(
                        AvailabilitySlot(
                            staff_id=staff_id,
                            staff_name=staff_name,
                            start_time=slot_start,
                            end_time=slot_end,
                        )
                    )

    return sorted(slots, key=lambda slot: (slot.start_time, slot.staff_name))
