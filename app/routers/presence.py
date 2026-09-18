from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.checkin import PresenceCount
from app.services.presence import current_presence_count

router = APIRouter(prefix="/presence", tags=["presence"])


@router.get("/count", response_model=PresenceCount)
async def presence_count(db: AsyncSession = Depends(get_db)) -> PresenceCount:
    return PresenceCount(current_count=await current_presence_count(db))
