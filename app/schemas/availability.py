import uuid
from datetime import datetime

from pydantic import BaseModel


class AvailabilitySlot(BaseModel):
    staff_id: uuid.UUID
    staff_name: str
    start_time: datetime
    end_time: datetime


class AvailabilityResponse(BaseModel):
    service_id: uuid.UUID
    date: str
    slots: list[AvailabilitySlot]
