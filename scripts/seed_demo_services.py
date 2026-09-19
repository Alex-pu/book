import argparse
import asyncio
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import async_connect_args, async_database_url
from app.models.catalog import Service, ServiceCapacityWindow


DEMO_SERVICES = [
    {
        "name": "Massage",
        "description": "Demo massage service",
        "duration_min": 60,
        "capacity_mode": "worker",
        "capacity_limit": 1,
        "requires_worker": True,
        "daily_capacity": 2,
    },
    {
        "name": "Facial",
        "description": "Demo facial service",
        "duration_min": 45,
        "capacity_mode": "worker",
        "capacity_limit": 1,
        "requires_worker": True,
        "daily_capacity": 2,
    },
    {
        "name": "Sauna",
        "description": "Demo shared sauna service",
        "duration_min": 60,
        "capacity_mode": "shared",
        "capacity_limit": 20,
        "requires_worker": False,
        "daily_capacity": 20,
    },
    {
        "name": "Steam Bath",
        "description": "Demo shared steam bath service",
        "duration_min": 45,
        "capacity_mode": "shared",
        "capacity_limit": 10,
        "requires_worker": False,
        "daily_capacity": 10,
    },
    {
        "name": "Body Scrub",
        "description": "Demo body scrub service",
        "duration_min": 45,
        "capacity_mode": "worker",
        "capacity_limit": 1,
        "requires_worker": True,
        "daily_capacity": 2,
    },
]


async def seed_demo_services(*, days: int) -> None:
    settings = get_settings()
    engine = create_async_engine(
        async_database_url(settings.database_url),
        pool_pre_ping=True,
        connect_args=async_connect_args(settings.database_url),
    )
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    eat = timezone(timedelta(hours=3))
    today = datetime.now(eat).date()

    async with sessionmaker() as session:
        async with session.begin():
            for spec in DEMO_SERVICES:
                row = await session.execute(select(Service).where(Service.name == spec["name"]))
                service = row.scalars().first()
                if service is None:
                    service = Service(name=spec["name"])
                    session.add(service)

                service.description = spec["description"]
                service.duration_min = spec["duration_min"]
                service.price_kes = Decimal("1.00")
                service.capacity_mode = spec["capacity_mode"]
                service.capacity_limit = spec["capacity_limit"]
                service.requires_worker = spec["requires_worker"]
                service.is_active = True
                await session.flush()

                await session.execute(
                    delete(ServiceCapacityWindow).where(
                        ServiceCapacityWindow.service_id == service.id,
                        ServiceCapacityWindow.note == "Demo seed",
                    )
                )

                for offset in range(days):
                    day = today + timedelta(days=offset)
                    session.add(
                        ServiceCapacityWindow(
                            service_id=service.id,
                            start_time=datetime.combine(day, time(9, 0), tzinfo=eat),
                            end_time=datetime.combine(day, time(20, 0), tzinfo=eat),
                            capacity=spec["daily_capacity"],
                            note="Demo seed",
                        )
                    )

    await engine.dispose()
    print(f"Seeded {len(DEMO_SERVICES)} demo services at KES 1.00 with {days} days of capacity.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo spa services and capacity windows.")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    asyncio.run(seed_demo_services(days=args.days))


if __name__ == "__main__":
    main()
