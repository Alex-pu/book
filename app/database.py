from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def async_database_url(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+asyncpg")
    elif url.drivername == "postgresql+psycopg":
        url = url.set(drivername="postgresql+asyncpg")

    if url.drivername == "postgresql+asyncpg":
        query = dict(url.query)
        query.pop("sslmode", None)
        query.pop("channel_binding", None)
        query.pop("ssl", None)
        url = url.set(query=query)

    return url.render_as_string(hide_password=False)


def async_connect_args(database_url: str) -> dict:
    url = make_url(database_url)
    sslmode = url.query.get("sslmode")
    if sslmode in {"require", "verify-ca", "verify-full"}:
        return {"ssl": True}
    return {}


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            async_database_url(settings.database_url),
            pool_pre_ping=True,
            connect_args=async_connect_args(settings.database_url),
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_sessionmaker()() as session:
        yield session
