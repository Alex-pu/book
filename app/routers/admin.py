from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.database import get_db
from app.models.staff import Staff
from app.schemas.payment import DisbursementRead, PaymentLedgerItem
from app.services.disbursements import create_disbursement_batch, list_disbursements, payment_ledger

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/disbursements", response_model=list[DisbursementRead])
async def disbursements(
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> list[DisbursementRead]:
    return await list_disbursements(db)


@router.post(
    "/disbursements/run",
    response_model=DisbursementRead | None,
    status_code=status.HTTP_201_CREATED,
)
async def run_disbursement(
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> DisbursementRead | None:
    async with db.begin():
        return await create_disbursement_batch(db)


@router.get("/payments", response_model=list[PaymentLedgerItem])
async def payments(
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(require_admin),
) -> list[PaymentLedgerItem]:
    return await payment_ledger(db, from_time=from_time, to_time=to_time)
