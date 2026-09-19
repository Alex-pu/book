import base64
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.booking import Booking
from app.models.payment import Payment
from app.services.fees import calculate_fee
from app.services.scheduling import PENDING_PAYMENT, SlotUnavailableError, now_utc, total_booking_amount
from app.services.sms import booking_confirmed_message, queue_notification


SUCCESS_RESULT_CODE = 0


def booking_account_reference(booking_id: uuid.UUID) -> str:
    return f"SPA{booking_id.hex[:9]}"


class DarajaError(RuntimeError):
    pass


@dataclass(frozen=True)
class StkPushResult:
    checkout_request_id: str
    raw_response: dict


@dataclass(frozen=True)
class StkPushQueryResult:
    checkout_request_id: str
    result_code: str | None
    result_description: str | None
    response_code: str | None
    response_description: str | None
    raw_response: dict


@dataclass(frozen=True)
class ParsedStkCallback:
    checkout_request_id: str | None
    result_code: int | None
    result_description: str | None
    amount: Decimal | None
    mpesa_receipt_number: str | None
    phone_number: str | None
    transaction_date: str | None

    @property
    def succeeded(self) -> bool:
        return self.result_code == SUCCESS_RESULT_CODE


class DarajaClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def base_url(self) -> str:
        if self.settings.daraja_env == "sandbox":
            return "https://sandbox.safaricom.co.ke"
        return "https://api.safaricom.co.ke"

    def _ensure_configured(self) -> None:
        required = {
            "DARAJA_CONSUMER_KEY": self.settings.daraja_consumer_key,
            "DARAJA_CONSUMER_SECRET": self.settings.daraja_consumer_secret,
            "DARAJA_SHORTCODE": self.settings.daraja_shortcode,
            "DARAJA_PASSKEY": self.settings.daraja_passkey,
            "DARAJA_CALLBACK_BASE_URL": self.settings.daraja_callback_base_url,
        }
        missing = [
            name for name, value in required.items() if not value or value.strip().lower() == "undefined"
        ]
        if missing:
            raise DarajaError(
                "Daraja STK Push is not fully configured. Missing: " + ", ".join(missing)
            )

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        response = await client.get(
            f"{self.base_url}/oauth/v1/generate",
            params={"grant_type": "client_credentials"},
            auth=(self.settings.daraja_consumer_key, self.settings.daraja_consumer_secret),
        )
        self._raise_for_status(response, "access token request")
        token = response.json().get("access_token")
        if not token:
            raise DarajaError("Daraja access token response did not include access_token")
        return token

    def _stk_password(self, timestamp: str) -> str:
        password_value = (
            f"{self.settings.daraja_shortcode}{self.settings.daraja_passkey}{timestamp}"
        )
        return base64.b64encode(password_value.encode("utf-8")).decode("utf-8")

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        value = re.sub(r"[\s()-]", "", phone)
        if value.startswith("+"):
            value = value[1:]
        if value.startswith("07") or value.startswith("01"):
            value = "254" + value[1:]
        if not re.fullmatch(r"254\d{9}", value):
            raise DarajaError("Use a valid Kenyan M-Pesa number, for example 0712345678")
        return value

    @staticmethod
    def _raise_for_status(response: httpx.Response, operation: str) -> None:
        try:
            response.raise_for_status()
            return
        except httpx.HTTPStatusError:
            pass
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:500]
        raise DarajaError(f"Daraja {operation} failed ({response.status_code}): {detail}")

    async def initiate_stk_push(
        self,
        *,
        phone: str,
        amount: Decimal,
        booking_id: uuid.UUID,
    ) -> StkPushResult:
        self._ensure_configured()
        phone = self._normalize_phone(phone)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = self._stk_password(timestamp)
        callback_url = f"{self.settings.daraja_callback_base_url.rstrip('/')}/api/v1/payments/callback"

        payload = {
            "BusinessShortCode": self.settings.daraja_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": self.settings.daraja_stk_transaction_type,
            "Amount": int(amount),
            "PartyA": phone,
            "PartyB": self.settings.daraja_shortcode,
            "PhoneNumber": phone,
            "CallBackURL": callback_url,
            "AccountReference": booking_account_reference(booking_id),
            "TransactionDesc": "Spa booking",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._access_token(client)
            response = await client.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
            self._raise_for_status(response, "STK query")
            data = response.json()

        checkout_request_id = data.get("CheckoutRequestID")
        if not checkout_request_id:
            raise DarajaError("Daraja STK Push response did not include CheckoutRequestID")
        return StkPushResult(checkout_request_id=checkout_request_id, raw_response=data)

    async def query_stk_push(self, *, checkout_request_id: str) -> StkPushQueryResult:
        self._ensure_configured()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        payload = {
            "BusinessShortCode": self.settings.daraja_shortcode,
            "Password": self._stk_password(timestamp),
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._access_token(client)
            response = await client.post(
                f"{self.base_url}/mpesa/stkpushquery/v1/query",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
            self._raise_for_status(response, "STK Push")
            data = response.json()

        return StkPushQueryResult(
            checkout_request_id=checkout_request_id,
            result_code=data.get("ResultCode"),
            result_description=data.get("ResultDesc"),
            response_code=data.get("ResponseCode"),
            response_description=data.get("ResponseDescription"),
            raw_response=data,
        )


def parse_stk_callback(payload: dict) -> ParsedStkCallback:
    callback = payload.get("Body", {}).get("stkCallback", {})
    metadata_items = callback.get("CallbackMetadata", {}).get("Item", [])
    metadata = {
        item.get("Name"): item.get("Value")
        for item in metadata_items
        if isinstance(item, dict) and item.get("Name")
    }

    amount = metadata.get("Amount")
    return ParsedStkCallback(
        checkout_request_id=callback.get("CheckoutRequestID"),
        result_code=callback.get("ResultCode"),
        result_description=callback.get("ResultDesc"),
        amount=Decimal(str(amount)) if amount is not None else None,
        mpesa_receipt_number=metadata.get("MpesaReceiptNumber"),
        phone_number=str(metadata["PhoneNumber"]) if metadata.get("PhoneNumber") is not None else None,
        transaction_date=str(metadata["TransactionDate"])
        if metadata.get("TransactionDate") is not None
        else None,
    )


async def initiate_booking_payment(
    db: AsyncSession,
    *,
    booking_id: uuid.UUID,
    settings: Settings,
    daraja_client: DarajaClient | None = None,
) -> Payment:
    row = await db.execute(
        select(Booking)
        .options(selectinload(Booking.items))
        .where(Booking.id == booking_id)
        .with_for_update()
    )
    booking = row.scalar_one_or_none()
    if booking is None:
        raise SlotUnavailableError("Booking not found")

    if booking.status != PENDING_PAYMENT:
        raise SlotUnavailableError("Booking is not awaiting payment")

    amount = total_booking_amount(booking.items)
    if amount <= 0:
        raise SlotUnavailableError("Booking has no payable items")

    fee, net = calculate_fee(amount, Decimal(str(settings.platform_fee_percent)))
    payment = Payment(
        booking_id=booking.id,
        amount_kes=amount,
        platform_fee_kes=fee,
        net_to_forward_kes=net,
        status="initiated",
    )
    db.add(payment)
    await db.flush()

    client = daraja_client or DarajaClient(settings)
    stk_result = await client.initiate_stk_push(
        phone=booking.customer_phone,
        amount=amount,
        booking_id=booking.id,
    )
    payment.checkout_request_id = stk_result.checkout_request_id
    await db.flush()
    await db.refresh(payment)
    return payment


async def handle_stk_callback(db: AsyncSession, payload: dict) -> Payment | None:
    parsed = parse_stk_callback(payload)
    if not parsed.checkout_request_id:
        return None

    row = await db.execute(
        select(Payment, Booking)
        .join(Booking, Booking.id == Payment.booking_id)
        .where(Payment.checkout_request_id == parsed.checkout_request_id)
        .with_for_update()
    )
    result = row.one_or_none()
    if result is None:
        return None

    payment, booking = result
    if payment.status in {"success", "failed", "cancelled"}:
        return payment

    payment.raw_callback_payload = payload
    payment.completed_at = now_utc()

    if parsed.succeeded:
        payment.status = "success"
        payment.mpesa_receipt_number = parsed.mpesa_receipt_number
        booking.status = "confirmed"
        booking.lock_expires_at = None
        message = booking_confirmed_message(booking)
        await queue_notification(
            db,
            booking_id=booking.id,
            phone=message.phone,
            template=message.template,
            body=message.body,
        )
    else:
        payment.status = "failed"
        if booking.status == PENDING_PAYMENT:
            booking.status = "expired"

    booking.updated_at = now_utc()
    await db.flush()
    await db.refresh(payment)
    return payment
