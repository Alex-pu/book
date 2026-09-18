import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ServiceRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    duration_min: int
    price_kes: Decimal
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
