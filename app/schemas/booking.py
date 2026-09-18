import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BookingCreate(BaseModel):
    service_id: uuid.UUID
    staff_id: uuid.UUID
    start_time: datetime
    customer_name: str = Field(min_length=1, max_length=200)
    customer_phone: str = Field(min_length=7, max_length=32)


class BookingCreated(BaseModel):
    booking_id: uuid.UUID
    status: str
    lock_expires_at: datetime


class BookingStatus(BaseModel):
    id: uuid.UUID
    status: str
    lock_expires_at: datetime | None
    start_time: datetime
    end_time: datetime

    model_config = ConfigDict(from_attributes=True)
