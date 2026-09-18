import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BookingServiceCreate(BaseModel):
    service_id: uuid.UUID
    quantity: int | None = Field(default=None, ge=1, le=100)


class BookingCreate(BaseModel):
    service_id: uuid.UUID | None = None
    services: list[BookingServiceCreate] | None = Field(default=None, min_length=1, max_length=20)
    staff_id: uuid.UUID | None = None
    start_time: datetime
    customer_name: str = Field(min_length=1, max_length=200)
    customer_phone: str = Field(min_length=7, max_length=32)
    party_size: int = Field(default=1, ge=1, le=100)

    @model_validator(mode="after")
    def require_service_selection(self) -> "BookingCreate":
        if self.service_id is None and not self.services:
            raise ValueError("Either service_id or services is required")
        return self


class BookingLineRead(BaseModel):
    service_id: uuid.UUID
    quantity: int
    unit_price_kes: Decimal
    line_total_kes: Decimal

    model_config = ConfigDict(from_attributes=True)


class BookingScheduleRead(BaseModel):
    service_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    units: int

    model_config = ConfigDict(from_attributes=True)


class BookingCreated(BaseModel):
    booking_id: uuid.UUID
    status: str
    lock_expires_at: datetime
    start_time: datetime
    end_time: datetime
    party_size: int
    total_amount_kes: Decimal
    items: list[BookingLineRead]
    schedule: list[BookingScheduleRead]


class BookingStatus(BaseModel):
    id: uuid.UUID
    status: str
    lock_expires_at: datetime | None
    start_time: datetime
    end_time: datetime
    party_size: int
    source: str
    staff_id: uuid.UUID | None = None

    model_config = ConfigDict(from_attributes=True)
