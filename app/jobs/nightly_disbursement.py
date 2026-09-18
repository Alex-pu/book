import asyncio

from app.database import get_sessionmaker
from app.services.disbursements import create_disbursement_batch


async def run_once() -> str:
    async with get_sessionmaker()() as db:
        async with db.begin():
            disbursement = await create_disbursement_batch(db)
            if disbursement is None:
                return "No successful payments pending disbursement."
            return f"Created disbursement {disbursement.id} for {disbursement.payment_count} payment(s)."


if __name__ == "__main__":
    print(asyncio.run(run_once()))
