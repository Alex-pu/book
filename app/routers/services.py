from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.catalog import Service
from app.schemas.catalog import ServiceRead

router = APIRouter(prefix="/services", tags=["services"])


@router.get("", response_model=list[ServiceRead])
async def list_services(db: AsyncSession = Depends(get_db)) -> list[Service]:
    result = await db.execute(
        select(Service).where(Service.is_active.is_(True)).order_by(Service.name)
    )
    return list(result.scalars())
