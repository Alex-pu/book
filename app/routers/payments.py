from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.deps import get_current_staff
from app.database import get_db
from app.models.staff import Staff
from app.schemas.payment import (
    CallbackPaymentStatus,
    DarajaAcceptedResponse,
    StkPushQueryResponse,
    StkPushRequest,
    StkPushResponse,
)
from app.services.daraja import (
    DarajaClient,
    DarajaError,
    booking_account_reference,
    handle_stk_callback,
    initiate_booking_payment,
)
from app.services.scheduling import SlotUnavailableError

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/stk-push", response_model=StkPushResponse)
async def stk_push(
    payload: StkPushRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StkPushResponse:
    try:
        async with db.begin():
            payment = await initiate_booking_payment(
                db,
                booking_id=payload.booking_id,
                settings=settings,
            )
    except SlotUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DarajaError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return StkPushResponse(
        payment_id=payment.id,
        checkout_request_id=payment.checkout_request_id,
        paybill_shortcode=settings.daraja_shortcode,
        account_reference=booking_account_reference(payload.booking_id),
    )


@router.post("/callback", response_model=DarajaAcceptedResponse)
async def payment_callback(
    payload: dict,
    db: AsyncSession = Depends(get_db),
) -> DarajaAcceptedResponse:
    async with db.begin():
        await handle_stk_callback(db, payload)

    return DarajaAcceptedResponse()


@router.get("/callback-status", response_model=CallbackPaymentStatus)
async def callback_status(
    account_reference: str,
    phone: str,
    db: AsyncSession = Depends(get_db),
) -> CallbackPaymentStatus:
    from sqlalchemy import select
    from app.models.booking import Booking
    from app.models.payment import Payment
    from app.services.daraja import booking_account_reference

    bookings = (
        await db.execute(
            select(Booking)
            .where(Booking.customer_phone == phone.strip())
            .order_by(Booking.created_at.desc())
            .limit(20)
        )
    ).scalars()
    booking = next(
        (
            item
            for item in bookings
            if booking_account_reference(item.id).lower() == account_reference.strip().lower()
        ),
        None,
    )
    if booking is None:
        return CallbackPaymentStatus(
            booking_id=None,
            booking_status=None,
            payment_status=None,
            receipt_number=None,
            confirmed=False,
            message="Payment callback not found. Please try again later.",
        )
    payment = (
        await db.execute(
            select(Payment)
            .where(Payment.booking_id == booking.id)
            .order_by(Payment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    confirmed = bool(payment and payment.status == "success" and booking.status == "confirmed")
    return CallbackPaymentStatus(
        booking_id=booking.id,
        booking_status=booking.status,
        payment_status=payment.status if payment else None,
        receipt_number=payment.mpesa_receipt_number if payment else None,
        confirmed=confirmed,
        message=(
            "Payment confirmed by callback."
            if confirmed
            else "Payment callback not received yet. Please try again later."
        ),
    )


@router.post("/stk-push/{checkout_request_id}/query", response_model=StkPushQueryResponse)
async def query_stk_push(
    checkout_request_id: str,
    settings: Settings = Depends(get_settings),
    current_staff: Staff = Depends(get_current_staff),
) -> StkPushQueryResponse:
    try:
        result = await DarajaClient(settings).query_stk_push(
            checkout_request_id=checkout_request_id
        )
    except DarajaError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return StkPushQueryResponse(
        checkout_request_id=result.checkout_request_id,
        result_code=result.result_code,
        result_description=result.result_description,
        response_code=result.response_code,
        response_description=result.response_description,
        raw_response=result.raw_response,
    )
