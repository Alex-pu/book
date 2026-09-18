import argparse
import asyncio

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.security import hash_password
from app.database import async_connect_args, async_database_url
from app.models.staff import Staff


async def seed_admin(*, email: str, password: str, full_name: str) -> None:
    settings = get_settings()
    engine = create_async_engine(
        async_database_url(settings.database_url),
        pool_pre_ping=True,
        connect_args=async_connect_args(settings.database_url),
    )
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    normalized_email = email.strip().lower()

    async with sessionmaker() as session:
        async with session.begin():
            row = await session.execute(
                select(Staff).where(
                    or_(Staff.email == normalized_email, Staff.phone == normalized_email)
                )
            )
            staff = row.scalar_one_or_none()
            if staff is None:
                staff = Staff(
                    full_name=full_name.strip(),
                    phone=normalized_email,
                    email=normalized_email,
                    role="admin",
                    password_hash=hash_password(password),
                    is_active=True,
                )
                session.add(staff)
            else:
                staff.full_name = full_name.strip()
                staff.phone = normalized_email
                staff.email = normalized_email
                staff.role = "admin"
                staff.password_hash = hash_password(password)
                staff.is_active = True

    await engine.dispose()
    print(f"Seeded admin account for {normalized_email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed or update an admin staff account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--full-name", default="Admin")
    args = parser.parse_args()

    asyncio.run(
        seed_admin(
            email=args.email,
            password=args.password,
            full_name=args.full_name,
        )
    )


if __name__ == "__main__":
    main()
