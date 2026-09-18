import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.booking import BookingStatus


class StaffBlockCreate(BaseModel):
    start_time: datetime
    end_time: datetime
    note: str | None = Field(default=None, max_length=500)


class StaffBlockRead(BaseModel):
    id: uuid.UUID
    staff_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    is_available: bool
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StaffBookingsResponse(BaseModel):
    staff_id: uuid.UUID
    bookings: list[BookingStatus]
