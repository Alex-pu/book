import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator


class CheckinCreate(BaseModel):
    booking_id: uuid.UUID | None = None
    customer_name: str | None = None

    @model_validator(mode="after")
    def require_booking_or_customer_name(self) -> "CheckinCreate":
        if self.booking_id is None and not self.customer_name:
            raise ValueError("booking_id or customer_name is required")
        return self


class CheckinRead(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID | None
    customer_name: str | None
    checked_in_at: datetime
    checked_out_at: datetime | None
    checked_in_by: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class PresenceCount(BaseModel):
    current_count: int
