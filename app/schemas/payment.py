import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StkPushRequest(BaseModel):
    booking_id: uuid.UUID


class ManualPaymentConfirmation(BaseModel):
    booking_id: uuid.UUID
    receipt_number: str = Field(min_length=5, max_length=40)


class StkPushResponse(BaseModel):
    payment_id: uuid.UUID
    checkout_request_id: str
    paybill_shortcode: str | None = None
    account_reference: str | None = None


class DarajaCallbackResponse(BaseModel):
    processed: bool
    checkout_request_id: str | None = None
    status: str | None = None


class DarajaAcceptedResponse(BaseModel):
    ResultCode: int = 0
    ResultDesc: str = "Accepted"


class StkPushQueryResponse(BaseModel):
    checkout_request_id: str
    result_code: str | None = None
    result_description: str | None = None
    response_code: str | None = None
    response_description: str | None = None
    raw_response: dict


class PaymentLedgerItem(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    checkout_request_id: str | None
    mpesa_receipt_number: str | None
    amount_kes: Decimal
    platform_fee_kes: Decimal
    net_to_forward_kes: Decimal
    status: str
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class DisbursementRead(BaseModel):
    id: uuid.UUID
    period_start: datetime
    period_end: datetime
    total_amount_kes: Decimal
    payment_count: int
    daraja_conversation_id: str | None
    status: str
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
