import asyncio
import uuid
from decimal import Decimal

from app.config import Settings
from app.services.daraja import DarajaClient, parse_stk_callback


def test_production_base_url() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/test",
        JWT_SECRET="secret",
        DARAJA_ENV="production",
    )

    assert DarajaClient(settings).base_url == "https://api.safaricom.co.ke"


def test_stk_password_generation() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/test",
        JWT_SECRET="secret",
        DARAJA_SHORTCODE="123456",
        DARAJA_PASSKEY="passkey",
    )

    assert DarajaClient(settings)._stk_password("20260918120000")


def test_initiate_stk_push_payload_shape(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            return FakeResponse({"access_token": "token"})

        async def post(self, url, *, headers, json):
            captured["url"] = url
            captured["payload"] = json
            return FakeResponse({"CheckoutRequestID": "ws_CO_live_test"})

    monkeypatch.setattr("app.services.daraja.httpx.AsyncClient", FakeAsyncClient)
    settings = Settings(
        DATABASE_URL="postgresql://user:pass@localhost/test",
        JWT_SECRET="secret",
        DARAJA_CONSUMER_KEY="key",
        DARAJA_CONSUMER_SECRET="secret",
        DARAJA_SHORTCODE="123456",
        DARAJA_PASSKEY="passkey",
        DARAJA_CALLBACK_BASE_URL="https://example.com",
        DARAJA_STK_TRANSACTION_TYPE="CustomerPayBillOnline",
    )
    booking_id = uuid.uuid4()

    result = asyncio.run(
        DarajaClient(settings).initiate_stk_push(
            phone="254712345678",
            amount=Decimal("100.00"),
            booking_id=booking_id,
        )
    )

    assert result.checkout_request_id == "ws_CO_live_test"
    assert captured["url"] == "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    assert captured["payload"]["TransactionType"] == "CustomerPayBillOnline"
    assert captured["payload"]["AccountReference"] == f"SPA{booking_id.hex[:9]}"
    assert len(captured["payload"]["AccountReference"]) == 12
    assert captured["payload"]["TransactionDesc"] == "Spa booking"


def test_parse_successful_stk_callback() -> None:
    payload = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "ws_CO_123",
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 1500},
                        {"Name": "MpesaReceiptNumber", "Value": "TIS123ABC"},
                        {"Name": "TransactionDate", "Value": 20260918103045},
                        {"Name": "PhoneNumber", "Value": 254712345678},
                    ]
                },
            }
        }
    }

    parsed = parse_stk_callback(payload)

    assert parsed.checkout_request_id == "ws_CO_123"
    assert parsed.succeeded is True
    assert parsed.amount == Decimal("1500")
    assert parsed.mpesa_receipt_number == "TIS123ABC"
    assert parsed.phone_number == "254712345678"
    assert parsed.transaction_date == "20260918103045"


def test_parse_failed_stk_callback_without_metadata() -> None:
    payload = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "ws_CO_456",
                "ResultCode": 1032,
                "ResultDesc": "Request cancelled by user.",
            }
        }
    }

    parsed = parse_stk_callback(payload)

    assert parsed.checkout_request_id == "ws_CO_456"
    assert parsed.succeeded is False
    assert parsed.amount is None
    assert parsed.mpesa_receipt_number is None
