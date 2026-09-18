import asyncio

from sqlalchemy import text

from app.database import get_engine


async def main() -> None:
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            table_count = await conn.scalar(
                text("select count(*) from information_schema.tables where table_schema = 'public'")
            )
            print(f"public_tables={table_count}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
