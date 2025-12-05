from typing import AsyncIterator, Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db import get_engine


async def get_transaction_dependency() -> AsyncIterator[AsyncConnection]:
    engine = get_engine()
    async with engine.connect() as conn:
        async with conn.begin():
            yield conn


DbTransaction = Annotated[AsyncConnection, Depends(get_transaction_dependency)]
