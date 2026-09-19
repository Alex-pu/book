from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.payment import Payment
from app.services.scheduling import PENDING_PAYMENT, now_utc

FINAL_PAYMENT_STATUSES = {"success", "failed", "cancelled"}


async def expire_pending_payment_locks(db: AsyncSession) -> int:
    moment = now_utc()
    rows = await db.execute(
        select(Booking)
        .where(
            Booking.status == PENDING_PAYMENT,
            Booking.lock_expires_at.is_not(None),
            Booking.lock_expires_at < moment,
        )
        .with_for_update()
    )
    bookings = list(rows.scalars())
    expired = 0

    for booking in bookings:
        successful_payment = await db.execute(
            select(Payment.id).where(
                Payment.booking_id == booking.id,
                Payment.status == "success",
            )
        )
        if successful_payment.scalar_one_or_none() is not None:
            booking.status = "confirmed"
            booking.lock_expires_at = None
        else:
            booking.status = "expired"
        booking.updated_at = moment
        expired += 1

    await db.flush()
    return expired


async def cancel_confirmed_booking(db: AsyncSession, booking_id) -> Booking:
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise ValueError("Booking not found")
    if booking.status not in {"confirmed", "checked_in"}:
        raise ValueError("Only confirmed or checked-in bookings can be cancelled")

    booking.status = "cancelled"
    booking.updated_at = now_utc()
    await db.flush()
    await db.refresh(booking)
    return booking
