import uuid
from datetime import datetime

from pydantic import BaseModel


class AvailabilitySlot(BaseModel):
    start_time: datetime
    end_time: datetime
    available_capacity: int


class AvailabilityResponse(BaseModel):
    service_id: uuid.UUID
    date: str
    slots: list[AvailabilitySlot]
