from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db_models import raw_event, RawEventStatus
from app.models import PostHogEvent, RawEvent, RawEventUpdate


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


async def update_raw_event(connection: AsyncConnection, raw_event_id: str, event: RawEventUpdate) -> None:
    stmt = raw_event.update().values(**event.model_dump()).where(raw_event.c.raw_event_id == raw_event_id)
    await connection.execute(stmt)


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

