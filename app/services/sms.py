import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.booking import Booking
from app.models.notification import NotificationLog


class SmsError(RuntimeError):
    pass


@dataclass(frozen=True)
class SmsMessage:
    phone: str
    template: str
    body: str


class SmsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, message: SmsMessage) -> str | None:
        if not self.settings.sms_api_key:
            return None

        payload = {
            "to": message.phone,
            "from": self.settings.sms_api_sender_id,
            "message": message.body,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.africastalking.com/version1/messaging",
                headers={"apiKey": self.settings.sms_api_key},
                data=payload,
            )
            response.raise_for_status()
            return response.text


def booking_confirmed_message(booking: Booking) -> SmsMessage:
    start = booking.start_time.strftime("%d %b %Y %H:%M")
    return SmsMessage(
        phone=booking.customer_phone,
        template="booking_confirmed",
        body=f"Your spa booking is confirmed for {start}. Thank you.",
    )


def checkout_thanks_message(phone: str) -> SmsMessage:
    return SmsMessage(
        phone=phone,
        template="checkin_thanks",
        body="Thank you for visiting. We hope to see you again soon.",
    )


async def queue_notification(
    db: AsyncSession,
    *,
    phone: str,
    template: str,
    body: str,
    booking_id: uuid.UUID | None = None,
    status: str = "queued",
    provider_ref: str | None = None,
) -> NotificationLog:
    notification = NotificationLog(
        booking_id=booking_id,
        phone=phone,
        template=template,
        body=body,
        status=status,
        provider_ref=provider_ref,
    )
    db.add(notification)
    await db.flush()
    await db.refresh(notification)
    return notification


async def send_and_log(
    db: AsyncSession,
    *,
    message: SmsMessage,
    settings: Settings,
    booking_id: uuid.UUID | None = None,
    sms_client: SmsClient | None = None,
) -> NotificationLog:
    client = sms_client or SmsClient(settings)
    status = "sent"
    provider_ref = None
    try:
        provider_ref = await client.send(message)
    except httpx.HTTPError as exc:
        status = "failed"
        provider_ref = str(exc)

    return await queue_notification(
        db,
        phone=message.phone,
        template=message.template,
        body=message.body,
        booking_id=booking_id,
        status=status,
        provider_ref=provider_ref,
    )
