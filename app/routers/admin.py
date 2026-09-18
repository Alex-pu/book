from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.core.security import hash_password
from app.database import get_db
from app.models.staff import Staff
from app.schemas.auth import AdminBootstrapRequest, AdminBootstrapResponse
from app.schemas.payment import DisbursementRead, PaymentLedgerItem
from app.services.disbursements import create_disbursement_batch, list_disbursements, payment_ledger

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/bootstrap", response_model=AdminBootstrapResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap_admin(
    payload: AdminBootstrapRequest,
    db: AsyncSession = Depends(get_db),
) -> AdminBootstrapResponse:
    phone = payload.phone or payload.email

    async with db.begin():
        existing_admin = await db.execute(select(Staff.id).where(Staff.role == "admin").limit(1))
        if existing_admin.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Admin account already exists",
            )

        row = await db.execute(
            select(Staff).where(or_(Staff.email == payload.email, Staff.phone == phone))
        )
        staff = row.scalar_one_or_none()

        if staff is None:
            staff = Staff(
                full_name=payload.full_name,
                phone=phone,
                email=payload.email,
                role="admin",
                password_hash=hash_password(payload.password),
                is_active=True,
            )
            db.add(staff)
        else:
            staff.full_name = payload.full_name
            staff.phone = phone
            staff.email = payload.email
            staff.role = "admin"
            staff.password_hash = hash_password(payload.password)
            staff.is_active = True

        await db.flush()
        await db.refresh(staff)

    return AdminBootstrapResponse(staff_id=staff.id, email=staff.email or payload.email, role=staff.role)


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
