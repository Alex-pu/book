import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin, require_super_admin
from app.core.security import hash_password
from app.database import get_db
from app.models.booking import Booking, BookingItem
from app.models.catalog import Service, ServiceCapacityWindow
from app.models.staff import Staff
from app.schemas.auth import (
    AdminBootstrapRequest,
    AdminBootstrapResponse,
    SpaAdminCreate,
    StaffAdminRead,
)
from app.schemas.booking import AdminBookingRead, BookingRescheduleRequest
from app.schemas.catalog import (
    ServiceCapacitySettingsUpdate,
    ServiceCapacityWindowCreate,
    ServiceCapacityWindowRead,
    ServiceCreate,
    ServiceRead,
    ServiceUpdate,
)
from app.schemas.payment import DisbursementRead, PaymentLedgerItem
from app.services.disbursements import create_disbursement_batch, list_disbursements, payment_ledger
from app.services.admin_bookings import reschedule_confirmed_booking
from app.services.scheduling import SchedulingError, SlotUnavailableError

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/services", response_model=list[ServiceRead])
async def admin_services(
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> list[Service]:
    rows = await db.execute(select(Service).order_by(Service.name, Service.created_at))
    return list(rows.scalars())


@router.post("/services", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
async def create_service(
    payload: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> Service:
    service = Service(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        duration_min=payload.duration_min,
        price_kes=payload.price_kes,
        capacity_mode=payload.capacity_mode,
        capacity_limit=payload.capacity_limit,
        requires_worker=payload.requires_worker,
        is_active=True,
    )
    db.add(service)
    await db.flush()
    await db.refresh(service)
    await db.commit()
    return service


@router.patch("/services/{service_id}", response_model=ServiceRead)
async def update_service(
    service_id: uuid.UUID,
    payload: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> Service:
    service = await db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    service.name = payload.name.strip()
    service.description = payload.description.strip() if payload.description else None
    service.duration_min = payload.duration_min
    service.price_kes = payload.price_kes
    service.capacity_mode = payload.capacity_mode
    service.capacity_limit = payload.capacity_limit
    service.requires_worker = payload.requires_worker
    service.is_active = payload.is_active
    await db.flush()
    await db.refresh(service)
    await db.commit()
    return service


def admin_booking_read(booking: Booking) -> AdminBookingRead:
    return AdminBookingRead(
        id=booking.id,
        customer_name=booking.customer_name,
        customer_phone=booking.customer_phone,
        party_size=booking.party_size,
        start_time=booking.start_time,
        end_time=booking.end_time,
        status=booking.status,
        service_ids=[item.service_id for item in booking.items],
        service_names=[item.service.name for item in booking.items],
        payments=booking.payments,
    )


@router.get("/bookings", response_model=list[AdminBookingRead])
async def all_bookings(
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> list[AdminBookingRead]:
    stmt = (
        select(Booking)
        .options(
            selectinload(Booking.items).selectinload(BookingItem.service),
            selectinload(Booking.payments),
        )
        .order_by(Booking.start_time)
    )
    if from_time is not None:
        stmt = stmt.where(Booking.start_time >= from_time)
    if to_time is not None:
        stmt = stmt.where(Booking.start_time < to_time)
    rows = await db.execute(stmt)
    return [admin_booking_read(booking) for booking in rows.scalars()]


@router.get("/bookings/confirmed", response_model=list[AdminBookingRead])
async def confirmed_bookings(
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> list[AdminBookingRead]:
    return await all_bookings(from_time, to_time, db, current_staff)


@router.get("/staff", response_model=list[StaffAdminRead])
async def list_admin_staff(
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> list[Staff]:
    rows = await db.execute(select(Staff).where(Staff.role.in_(["admin", "spa_admin"])).order_by(Staff.full_name))
    return list(rows.scalars())


@router.post("/staff", response_model=StaffAdminRead, status_code=status.HTTP_201_CREATED)
async def create_spa_admin(
    payload: SpaAdminCreate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_super_admin),
) -> Staff:
    async with db.begin():
        existing = await db.execute(
            select(Staff).where(or_(Staff.email == payload.email, Staff.phone == payload.phone))
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Staff email or phone already exists")
        staff = Staff(
            full_name=payload.full_name.strip(),
            email=payload.email,
            phone=payload.phone.strip(),
            role="spa_admin",
            password_hash=hash_password(payload.password),
            is_active=True,
        )
        db.add(staff)
        await db.flush()
        await db.refresh(staff)
    return staff


@router.patch("/bookings/{booking_id}/reschedule", response_model=AdminBookingRead)
async def reschedule_booking(
    booking_id: uuid.UUID,
    payload: BookingRescheduleRequest,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> AdminBookingRead:
    try:
        async with db.begin():
            row = await db.execute(
                select(Booking)
                .options(
                    selectinload(Booking.items).selectinload(BookingItem.service),
                    selectinload(Booking.schedule_items),
                    selectinload(Booking.payments),
                )
                .where(Booking.id == booking_id)
                .with_for_update()
            )
            booking = row.scalar_one_or_none()
            if booking is None:
                raise SlotUnavailableError("Booking not found")
            await reschedule_confirmed_booking(db, booking=booking, start_time=payload.start_time)
            response = admin_booking_read(booking)
        return response
    except SlotUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/bootstrap", response_model=AdminBootstrapResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap_admin(
    payload: AdminBootstrapRequest,
    db: AsyncSession = Depends(get_db),
) -> AdminBootstrapResponse:
    async with db.begin():
        existing_admin = await db.execute(select(Staff.id).where(Staff.role == "admin").limit(1))
        if existing_admin.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Admin account already exists",
            )

        row = await db.execute(
            select(Staff).where(or_(Staff.email == payload.email, Staff.phone == payload.email))
        )
        staff = row.scalar_one_or_none()

        if staff is None:
            staff = Staff(
                full_name=payload.full_name,
                phone=payload.email,
                email=payload.email,
                role="admin",
                password_hash=hash_password(payload.password),
                is_active=True,
            )
            db.add(staff)
        else:
            staff.full_name = payload.full_name
            staff.phone = payload.email
            staff.email = payload.email
            staff.role = "admin"
            staff.password_hash = hash_password(payload.password)
            staff.is_active = True

        await db.flush()
        await db.refresh(staff)

    return AdminBootstrapResponse(staff_id=staff.id, email=staff.email or payload.email, role=staff.role)


@router.patch("/services/{service_id}/capacity", response_model=ServiceRead)
async def update_service_capacity_settings(
    service_id: uuid.UUID,
    payload: ServiceCapacitySettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> Service:
    async with db.begin():
        service = await db.get(Service, service_id)
        if service is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
        service.capacity_mode = payload.capacity_mode
        service.capacity_limit = payload.capacity_limit
        if payload.requires_worker is not None:
            service.requires_worker = payload.requires_worker
        await db.flush()
        await db.refresh(service)
    return service


@router.post(
    "/service-capacity",
    response_model=ServiceCapacityWindowRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_service_capacity_window(
    payload: ServiceCapacityWindowCreate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> ServiceCapacityWindow:
    if payload.end_time <= payload.start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must be after start_time",
        )

    async with db.begin():
        service = await db.get(Service, payload.service_id)
        if service is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
        window = ServiceCapacityWindow(
            service_id=payload.service_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            capacity=payload.capacity,
            note=payload.note,
        )
        db.add(window)
        await db.flush()
        await db.refresh(window)
    return window


@router.get("/service-capacity", response_model=list[ServiceCapacityWindowRead])
async def list_service_capacity_windows(
    service_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> list[ServiceCapacityWindow]:
    stmt = select(ServiceCapacityWindow).order_by(ServiceCapacityWindow.start_time)
    if service_id is not None:
        stmt = stmt.where(ServiceCapacityWindow.service_id == service_id)
    rows = await db.execute(stmt)
    return list(rows.scalars())


@router.get("/disbursements", response_model=list[DisbursementRead])
async def disbursements(
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> list[DisbursementRead]:
    return await list_disbursements(db)


@router.post(
    "/disbursements/run",
    response_model=DisbursementRead | None,
    status_code=status.HTTP_201_CREATED,
)
async def run_disbursement(
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> DisbursementRead | None:
    async with db.begin():
        return await create_disbursement_batch(db)


@router.get("/payments", response_model=list[PaymentLedgerItem])
async def payments(
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> list[PaymentLedgerItem]:
    return await payment_ledger(db, from_time=from_time, to_time=to_time)
