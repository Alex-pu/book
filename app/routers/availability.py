import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.availability import AvailabilityResponse
from app.services.scheduling import list_available_slots

router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("", response_model=AvailabilityResponse)
async def get_availability(
    service_id: uuid.UUID = Query(...),
    date_: date = Query(..., alias="date"),
    db: AsyncSession = Depends(get_db),
) -> AvailabilityResponse:
    slots = await list_available_slots(db, service_id=service_id, day=date_)
    return AvailabilityResponse(service_id=service_id, date=date_.isoformat(), slots=slots)
