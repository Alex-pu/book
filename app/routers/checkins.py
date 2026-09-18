import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_staff
from app.database import get_db
from app.models.staff import Staff
from app.schemas.checkin import CheckinCreate, CheckinRead
from app.services.presence import checkout, create_checkin, open_checkins
from app.services.scheduling import SlotUnavailableError

router = APIRouter(prefix="/checkins", tags=["checkins"])


@router.post("", response_model=CheckinRead, status_code=status.HTTP_201_CREATED)
async def create_checkin_endpoint(
    payload: CheckinCreate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
) -> CheckinRead:
    try:
        async with db.begin():
            return await create_checkin(
                db,
                booking_id=payload.booking_id,
                customer_name=payload.customer_name,
                checked_in_by=current_staff.id,
            )
    except SlotUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/{checkin_id}/checkout", response_model=CheckinRead)
async def checkout_endpoint(
    checkin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
) -> CheckinRead:
    try:
        async with db.begin():
            return await checkout(db, checkin_id)
    except SlotUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/open", response_model=list[CheckinRead])
async def open_checkins_endpoint(
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
) -> list[CheckinRead]:
    return await open_checkins(db)
