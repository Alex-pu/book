import asyncio

from app.database import get_sessionmaker
from app.services.booking_state import expire_pending_payment_locks


async def run_once() -> int:
    async with get_sessionmaker()() as db:
        async with db.begin():
            return await expire_pending_payment_locks(db)


if __name__ == "__main__":
    expired_count = asyncio.run(run_once())
    print(f"Expired {expired_count} pending booking lock(s).")
