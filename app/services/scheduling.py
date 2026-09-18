import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingItem, BookingScheduleItem
from app.models.catalog import Service, ServiceCapacityWindow, staff_service
from app.models.staff import Staff, StaffAvailability
from app.schemas.availability import AvailabilitySlot
from app.schemas.booking import BookingServiceCreate

ACTIVE_CONFLICT_STATUSES = ("confirmed", "checked_in")
PENDING_PAYMENT = "pending_payment"
SLOT_STEP_MINUTES = 30
CAPACITY_MODES = {"worker", "shared", "private"}


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


def active_capacity_status_filter(moment: datetime):
    return or_(
        Booking.status.in_(ACTIVE_CONFLICT_STATUSES),
        and_(
            Booking.status == PENDING_PAYMENT,
            Booking.lock_expires_at.is_not(None),
            Booking.lock_expires_at > moment,
        ),
    )


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
    if service.capacity_mode not in CAPACITY_MODES:
        raise SchedulingError(f"Unsupported capacity mode: {service.capacity_mode}")
    return service


async def configured_capacity(
    db: AsyncSession,
    *,
    service: Service,
    start_time: datetime,
    end_time: datetime,
) -> int:
    start = ensure_aware(start_time)
    end = ensure_aware(end_time)
    rows = await db.execute(
        select(ServiceCapacityWindow.capacity)
        .where(
            ServiceCapacityWindow.service_id == service.id,
            ServiceCapacityWindow.start_time <= start,
            ServiceCapacityWindow.end_time >= end,
        )
        .order_by(ServiceCapacityWindow.capacity.desc())
    )
    configured = rows.scalars().first()
    if service.capacity_mode == "private":
        return min(configured or 0, 1)
    if configured is None:
        return 0
    if service.capacity_mode == "shared" and service.capacity_limit > 0:
        return min(configured, service.capacity_limit)
    return configured


async def used_capacity(
    db: AsyncSession,
    *,
    service_id: uuid.UUID,
    start_time: datetime,
    end_time: datetime,
    at_time: datetime,
) -> int:
    row = await db.execute(
        select(func.coalesce(func.sum(BookingScheduleItem.units), 0))
        .join(Booking, Booking.id == BookingScheduleItem.booking_id)
        .where(
            BookingScheduleItem.service_id == service_id,
            BookingScheduleItem.start_time < end_time,
            BookingScheduleItem.end_time > start_time,
            active_capacity_status_filter(at_time),
        )
    )
    return int(row.scalar_one())


async def available_capacity(
    db: AsyncSession,
    *,
    service: Service,
    start_time: datetime,
    end_time: datetime,
    at_time: datetime,
) -> int:
    capacity = await configured_capacity(
        db,
        service=service,
        start_time=start_time,
        end_time=end_time,
    )
    if capacity <= 0:
        return 0
    used = await used_capacity(
        db,
        service_id=service.id,
        start_time=start_time,
        end_time=end_time,
        at_time=at_time,
    )
    return max(capacity - used, 0)


def normalize_booking_lines(
    *,
    service_id: uuid.UUID | None,
    services: list[BookingServiceCreate] | None,
    party_size: int,
) -> list[BookingServiceCreate]:
    if services:
        return [
            BookingServiceCreate(
                service_id=line.service_id,
                quantity=line.quantity or party_size,
            )
            for line in services
        ]
    if service_id is None:
        raise SchedulingError("At least one service is required")
    return [BookingServiceCreate(service_id=service_id, quantity=party_size)]


async def schedule_service_units(
    db: AsyncSession,
    *,
    service: Service,
    quantity: int,
    start_time: datetime,
    at_time: datetime,
) -> list[BookingScheduleItem]:
    if quantity <= 0:
        raise SchedulingError("Service quantity must be positive")

    duration = timedelta(minutes=service.duration_min)
    if duration <= timedelta(0):
        raise SchedulingError("Service duration must be positive")

    remaining = quantity
    cursor = ensure_aware(start_time)
    schedule: list[BookingScheduleItem] = []
    attempts = 0
    max_attempts = 14 * 24 * (60 // SLOT_STEP_MINUTES)

    while remaining > 0:
        attempts += 1
        if attempts > max_attempts:
            raise SlotUnavailableError("No available capacity found for this service")

        end_time = cursor + duration
        if cursor <= at_time:
            cursor += timedelta(minutes=SLOT_STEP_MINUTES)
            continue

        capacity = await available_capacity(
            db,
            service=service,
            start_time=cursor,
            end_time=end_time,
            at_time=at_time,
        )
        if capacity <= 0:
            cursor += timedelta(minutes=SLOT_STEP_MINUTES)
            continue

        units = min(remaining, capacity)
        schedule.append(
            BookingScheduleItem(
                service_id=service.id,
                start_time=cursor,
                end_time=end_time,
                units=units,
            )
        )
        remaining -= units
        if remaining > 0:
            cursor = end_time

    return schedule


def total_booking_amount(items: list[BookingItem]) -> Decimal:
    return sum((item.line_total_kes for item in items), Decimal("0.00"))


async def create_soft_locked_booking(
    db: AsyncSession,
    *,
    service_id: uuid.UUID | None = None,
    services: list[BookingServiceCreate] | None = None,
    staff_id: uuid.UUID | None = None,
    start_time: datetime,
    customer_name: str,
    customer_phone: str,
    party_size: int = 1,
    lock_minutes: int,
    source: str = "online",
    created_by_staff_id: uuid.UUID | None = None,
) -> Booking:
    if lock_minutes <= 0:
        raise SchedulingError("Booking lock duration must be positive")
    if party_size <= 0:
        raise SchedulingError("Party size must be positive")

    moment = now_utc()
    start = ensure_aware(start_time)
    normalized_lines = normalize_booking_lines(
        service_id=service_id,
        services=services,
        party_size=party_size,
    )

    booking_items: list[BookingItem] = []
    schedule_items: list[BookingScheduleItem] = []
    current_start = start
    primary_service_id = normalized_lines[0].service_id

    for line in normalized_lines:
        service = await get_service_or_raise(db, line.service_id)
        quantity = line.quantity or party_size
        line_total = service.price_kes * quantity
        booking_items.append(
            BookingItem(
                service_id=service.id,
                quantity=quantity,
                unit_price_kes=service.price_kes,
                line_total_kes=line_total,
            )
        )
        service_schedule = await schedule_service_units(
            db,
            service=service,
            quantity=quantity,
            start_time=current_start,
            at_time=moment,
        )
        schedule_items.extend(service_schedule)
        current_start = max(item.end_time for item in service_schedule)

    if not schedule_items:
        raise SlotUnavailableError("No schedule could be generated for this booking")

    booking = Booking(
        service_id=primary_service_id,
        staff_id=staff_id,
        created_by_staff_id=created_by_staff_id,
        customer_name=customer_name.strip(),
        customer_phone=customer_phone.strip(),
        party_size=party_size,
        source=source,
        start_time=start,
        end_time=max(item.end_time for item in schedule_items),
        status=PENDING_PAYMENT,
        lock_expires_at=moment + timedelta(minutes=lock_minutes),
    )
    booking.items = booking_items
    booking.schedule_items = schedule_items
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

    slots: list[AvailabilitySlot] = []
    duration = timedelta(minutes=service.duration_min)
    cursor = max(day_start, moment + timedelta(minutes=SLOT_STEP_MINUTES))
    cursor = cursor.replace(second=0, microsecond=0)

    while cursor + duration <= day_end:
        slot_end = cursor + duration
        capacity = await available_capacity(
            db,
            service=service,
            start_time=cursor,
            end_time=slot_end,
            at_time=moment,
        )
        if capacity > 0:
            slots.append(
                AvailabilitySlot(
                    start_time=cursor,
                    end_time=slot_end,
                    available_capacity=capacity,
                )
            )
        cursor += timedelta(minutes=SLOT_STEP_MINUTES)

    return slots
