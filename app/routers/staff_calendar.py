import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import ensure_staff_scope, get_current_staff
from app.database import get_db
from app.models.staff import Staff
from app.schemas.staff import StaffBlockCreate, StaffBlockRead, StaffBookingsResponse
from app.services.scheduling import SchedulingError, SlotUnavailableError
from app.services.staff_calendar import create_staff_block, delete_staff_block, list_staff_bookings

router = APIRouter(prefix="/staff", tags=["staff-calendar"])


@router.get("/{staff_id}/bookings", response_model=StaffBookingsResponse)
async def staff_bookings(
    staff_id: uuid.UUID,
    date_: date = Query(..., alias="date"),
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
) -> StaffBookingsResponse:
    ensure_staff_scope(current_staff, staff_id)
    bookings = await list_staff_bookings(db, staff_id=staff_id, day=date_)
    return StaffBookingsResponse(staff_id=staff_id, bookings=bookings)


@router.post("/{staff_id}/blocks", response_model=StaffBlockRead, status_code=status.HTTP_201_CREATED)
async def create_block(
    staff_id: uuid.UUID,
    payload: StaffBlockCreate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
) -> StaffBlockRead:
    ensure_staff_scope(current_staff, staff_id)
    try:
        async with db.begin():
            return await create_staff_block(
                db,
                staff_id=staff_id,
                start_time=payload.start_time,
                end_time=payload.end_time,
                note=payload.note,
            )
    except SlotUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SchedulingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/{staff_id}/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    staff_id: uuid.UUID,
    block_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
) -> Response:
    ensure_staff_scope(current_staff, staff_id)
    try:
        async with db.begin():
            await delete_staff_block(db, staff_id=staff_id, block_id=block_id)
    except SlotUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
