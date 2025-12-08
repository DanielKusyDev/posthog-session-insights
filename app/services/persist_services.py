from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db_models import enriched_event, raw_event, session
from app.models import PostHogEvent, RawEvent, RawEventStatus, Session, EnrichedEventCreate
from app.services.event_parsing import EventType
from app.services.query_services import fetch_session


async def insert_raw_event(connection: AsyncConnection, event: PostHogEvent) -> None:
    stmt = raw_event.insert().values(
        event_name=event.event,
        user_id=event.distinct_id,
        timestamp=event.timestamp,
        properties=event.properties,
        status=RawEventStatus.pending.value,
        elements_chain=event.elements_chain,
    )
    await connection.execute(stmt)


async def update_raw_event_status(connection: AsyncConnection, raw_event_id: UUID, status: RawEventStatus) -> None:
    stmt = raw_event.update().values(status=status).where(raw_event.c.raw_event_id == raw_event_id)
    await connection.execute(stmt)


async def mark_event_as_failed(connection: AsyncConnection, event_id: UUID) -> None:
    await update_raw_event_status(connection, raw_event_id=event_id, status=RawEventStatus.failed)


async def mark_event_as_done(connection: AsyncConnection, event_id: UUID) -> None:
    await update_raw_event_status(connection, raw_event_id=event_id, status=RawEventStatus.done)


async def create_enriched_event(connection: AsyncConnection, input_data: EnrichedEventCreate) -> None:
    stmt = enriched_event.insert().values(**input_data.model_dump())
    await connection.execute(stmt)


async def get_or_create_session(connection: AsyncConnection, event: RawEvent) -> Session:
    # Try to insert, ignore if already exists
    insert_stmt = (
        insert(session)
        .values(
            session_id=event.session_id,
            user_id=event.user_id,
            started_at=event.timestamp,
            last_activity_at=event.timestamp,
            first_page=event.page_path,
            is_active=True,
        )
        .on_conflict_do_nothing(index_elements=["session_id"])
    )
    await connection.execute(insert_stmt)
    return await fetch_session(connection=connection, session_id=event.session_id)


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
