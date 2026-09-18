from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Disbursement, Payment, disbursement_payment
from app.services.scheduling import now_utc


def unbatched_successful_payments_statement() -> Select[tuple[Payment]]:
    return (
        select(Payment)
        .outerjoin(disbursement_payment, disbursement_payment.c.payment_id == Payment.id)
        .where(
            Payment.status == "success",
            disbursement_payment.c.payment_id.is_(None),
        )
        .order_by(Payment.completed_at, Payment.created_at)
        .with_for_update()
    )


async def create_disbursement_batch(db: AsyncSession) -> Disbursement | None:
    rows = await db.execute(unbatched_successful_payments_statement())
    payments = list(rows.scalars())
    if not payments:
        return None

    period_start = min(payment.completed_at or payment.created_at for payment in payments)
    period_end = now_utc()
    total = sum(payment.net_to_forward_kes for payment in payments)

    disbursement = Disbursement(
        period_start=period_start,
        period_end=period_end,
        total_amount_kes=total,
        payment_count=len(payments),
        status="pending",
    )
    disbursement.payments.extend(payments)
    db.add(disbursement)
    await db.flush()
    await db.refresh(disbursement)
    return disbursement


async def list_disbursements(db: AsyncSession) -> list[Disbursement]:
    rows = await db.execute(select(Disbursement).order_by(Disbursement.created_at.desc()))
    return list(rows.scalars())


async def payment_ledger(
    db: AsyncSession,
    *,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> list[Payment]:
    stmt = select(Payment).order_by(Payment.created_at.desc())
    if from_time is not None:
        stmt = stmt.where(Payment.created_at >= from_time)
    if to_time is not None:
        stmt = stmt.where(Payment.created_at <= to_time)
    rows = await db.execute(stmt)
    return list(rows.scalars())


async def undistributed_success_total(db: AsyncSession) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(Payment)
        .outerjoin(disbursement_payment, disbursement_payment.c.payment_id == Payment.id)
        .where(Payment.status == "success", disbursement_payment.c.payment_id.is_(None))
    )
    return int(count or 0)
