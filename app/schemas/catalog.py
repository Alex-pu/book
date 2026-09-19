import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ServiceRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    duration_min: int
    price_kes: Decimal
    capacity_mode: str
    capacity_limit: int
    requires_worker: bool
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceCapacitySettingsUpdate(BaseModel):
    capacity_mode: str = Field(pattern="^(worker|shared|private)$")
    capacity_limit: int = Field(default=1, ge=1, le=500)
    requires_worker: bool | None = None


class ServiceCapacityWindowCreate(BaseModel):
    service_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    capacity: int = Field(ge=0, le=500)
    note: str | None = None


class ServiceCapacityWindowRead(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    capacity: int
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
