from select import select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db_models import session
from app.models import Session, SessionCreate, SessionUpdate


async def fetch_session(connection: AsyncConnection, session_id: str) -> Session | None:
    stmt = select(session).where(session.c.session_id == session_id)
    result = await connection.execute(stmt)
    row = result.fetchone()
    if row:
        return Session.model_validate(row)
    return None


async def create_session(connection: AsyncConnection, input_data: SessionCreate) -> Session:
    """Create new session and return it using RETURNING clause"""
    stmt = session.insert().values(**input_data.model_dump()).returning(session)
    result = await connection.execute(stmt)
    row = result.fetchone()

    if not row:
        raise RuntimeError("Failed to create session - no row returned")

    return Session.model_validate(row)


async def update_session(connection: AsyncConnection, session_id: str, input_data: SessionUpdate) -> None:
    stmt = session.update().values(**input_data.model_dump()).where(session.c.session_id == session_id)
    await connection.execute(stmt)
