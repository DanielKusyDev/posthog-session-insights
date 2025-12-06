from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.config import settings

metadata = MetaData()

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("DB engine not initialized. Call init_db() first.")
    return _engine


async def init_db() -> None:
    global _engine

    _engine = create_async_engine(settings.sqlalchemy_url, echo=False, future=True)


@asynccontextmanager
async def get_connection() -> AsyncIterator[AsyncConnection]:
    engine = get_engine()
    async with engine.connect() as conn:
        yield conn


@asynccontextmanager
async def get_transaction() -> AsyncIterator[AsyncConnection]:
    engine = get_engine()
    async with engine.connect() as conn:
        async with conn.begin():
            yield conn
