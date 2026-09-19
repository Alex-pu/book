import uuid
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from reportlab.lib.pagesizes import A6
from reportlab.pdfgen import canvas

from app.config import Settings, get_settings
from app.core.deps import get_current_staff
from app.database import get_db
from app.models.booking import Booking
from app.models.booking import BookingItem, BookingScheduleItem
from app.models.staff import Staff
from app.schemas.booking import (
    BookingCreate,
    BookingCreated,
    BookingLineRead,
    BookingScheduleRead,
    BookingStatus,
)
from app.services.booking_state import cancel_confirmed_booking
from app.services.daraja import booking_account_reference
from app.services.scheduling import (
    SchedulingError,
    SlotUnavailableError,
    create_soft_locked_booking,
    total_booking_amount,
)

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("/search", response_model=list[BookingStatus])
async def search_bookings(
    phone: str = Query(..., min_length=7, max_length=32),
    db: AsyncSession = Depends(get_db),
) -> list[Booking]:
    rows = await db.execute(
        select(Booking)
        .where(Booking.customer_phone == phone.strip())
        .order_by(Booking.created_at.desc())
        .limit(20)
    )
    return list(rows.scalars())


@router.get("/lookup", response_model=list[BookingStatus])
async def lookup_bookings(
    account_reference: str = Query(..., min_length=5, max_length=40),
    phone: str = Query(..., min_length=7, max_length=32),
    db: AsyncSession = Depends(get_db),
) -> list[Booking]:
    reference = account_reference.strip().upper()
    rows = await db.execute(
        select(Booking)
        .where(
            Booking.customer_phone == phone.strip(),
        )
        .order_by(Booking.created_at.desc())
    )
    return [booking for booking in rows.scalars() if booking_account_reference(booking.id) == reference]


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
                services=payload.services,
                staff_id=payload.staff_id,
                start_time=payload.start_time,
                customer_name=payload.customer_name,
                customer_phone=payload.customer_phone,
                party_size=payload.party_size,
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
        start_time=booking.start_time,
        end_time=booking.end_time,
        party_size=booking.party_size,
        total_amount_kes=total_booking_amount(booking.items),
        paybill_shortcode=settings.daraja_shortcode,
        account_reference=booking_account_reference(booking.id),
        items=[BookingLineRead.model_validate(item) for item in booking.items],
        schedule=[BookingScheduleRead.model_validate(item) for item in booking.schedule_items],
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


@router.get("/{booking_id}/ticket", include_in_schema=False)
async def download_ticket(
    booking_id: uuid.UUID,
    phone: str = Query(..., min_length=7, max_length=32),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    row = await db.execute(
        select(Booking)
        .options(
            selectinload(Booking.items).selectinload(BookingItem.service),
            selectinload(Booking.schedule_items).selectinload(BookingScheduleItem.service),
        )
        .where(Booking.id == booking_id, Booking.customer_phone == phone.strip())
    )
    booking = row.scalar_one_or_none()
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status != "confirmed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking is not confirmed")

    document = BytesIO()
    pdf = canvas.Canvas(document, pagesize=A6)
    width, height = A6
    y = height - 42
    pdf.setTitle(f"Spa booking {booking.id}")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(28, y, "Kore Bench Spa")
    y -= 28
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(28, y, "BOOKING TICKET")
    y -= 24
    pdf.setFont("Helvetica", 9)
    pdf.drawString(28, y, f"Reference: {booking.id}")
    y -= 16
    pdf.drawString(28, y, f"Guest: {booking.customer_name}")
    y -= 16
    pdf.drawString(28, y, f"Phone: {booking.customer_phone}")
    y -= 24
    for item in booking.items:
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(28, y, f"{item.service.name} x{item.quantity}")
        y -= 16
    y -= 4
    for item in booking.schedule_items:
        pdf.setFont("Helvetica", 9)
        pdf.drawString(28, y, f"{item.start_time:%a %d %b %Y %I:%M %p}")
        y -= 14
        pdf.drawString(28, y, f"Until {item.end_time:%I:%M %p}")
        y -= 18
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(28, y, "Paid and confirmed")
    pdf.showPage()
    pdf.save()
    document.seek(0)
    filename = quote(f"spa-ticket-{booking.id}.pdf")
    return StreamingResponse(
        document,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
