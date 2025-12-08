from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db_models import raw_event, RawEventStatus, session
from app.models import RawEvent, Session


async def fetch_events_for_processing(connection: AsyncConnection, batch_size: int) -> list[RawEvent]:
    stmt = (
        select(raw_event)
        .where(raw_event.c.processed_at.is_(None), raw_event.c.status == RawEventStatus.pending)
        .order_by(raw_event.c.created_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    result = await connection.execute(stmt)
    rows = result.fetchall()
    return [RawEvent.model_validate(event) for event in rows]


async def fetch_session(connection: AsyncConnection, session_id: str) -> Session | None:
    stmt = select(session).where(session.c.session_id == session_id)
    result = await connection.execute(stmt)
    row = result.fetchone()
    if row:
        return Session.model_validate(row)
    return None
