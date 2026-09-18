import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.deps import get_current_staff
from app.database import get_db
from app.models.booking import Booking
from app.models.staff import Staff
from app.schemas.booking import BookingCreate, BookingCreated, BookingStatus
from app.services.booking_state import cancel_confirmed_booking
from app.services.scheduling import SchedulingError, SlotUnavailableError, create_soft_locked_booking

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingCreated, status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingCreate,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> BookingCreated:
    try:
        async with db.begin():
            booking = await create_soft_locked_booking(
                db,
                service_id=payload.service_id,
                staff_id=payload.staff_id,
                start_time=payload.start_time,
                customer_name=payload.customer_name,
                customer_phone=payload.customer_phone,
                lock_minutes=settings.booking_lock_minutes,
            )
    except SlotUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return BookingCreated(
        booking_id=booking.id,
        status=booking.status,
        lock_expires_at=booking.lock_expires_at,
    )


@router.get("/{booking_id}/status", response_model=BookingStatus)
async def get_booking_status(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Booking:
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


@router.patch("/{booking_id}/cancel", response_model=BookingStatus)
async def cancel_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
) -> Booking:
    try:
        async with db.begin():
            return await cancel_confirmed_booking(db, booking_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
