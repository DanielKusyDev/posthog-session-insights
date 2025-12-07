from select import select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db_models import session
from app.models import RawEvent, EnrichedEventCreate
from app.models import Session, SessionCreate
from app.services.event_parsing import EventType


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
    return Session.model_validate(row)


async def get_or_create_session(connection: AsyncConnection, event: RawEvent) -> Session:
    session = await fetch_session(connection=connection, session_id=event.session_id)

    if not session:
        new_session = SessionCreate(
            session_id=event.session_id,
            user_id=event.user_id,
            started_at=event.timestamp,
            last_activity_at=event.timestamp,
            first_page=event.page_path,
            is_active=True,
        )
        session = await create_session(connection=connection, input_data=new_session)
    return session


async def update_session_activity(
    connection: AsyncConnection, session_id: str, event: RawEvent, enriched_event: EnrichedEventCreate
) -> None:
    """Update session statistics after processing an event."""
    values = {
        "last_activity_at": event.timestamp,
        "event_count": session.c.event_count + 1,
    }

    if enriched_event.page_path:
        values["page_views_count"] = session.c.page_views_count + 1
        values["last_page"] = enriched_event.page_path
    elif enriched_event.event_type == EventType.click:
        values["clicks_count"] = session.c.clicks_count + 1

    # Update session
    stmt = session.update().where(session.c.session_id == session_id).values(**values)
    await connection.execute(stmt)
