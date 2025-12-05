from sqlalchemy.ext.asyncio import AsyncConnection

from app.db_models import raw_event, RawEventStatus
from app.models import PostHogEvent


async def insert_raw_event(connection: AsyncConnection, event: PostHogEvent) -> None:
    stmt = raw_event.insert().values(
        event_name=event.event,
        user_id=event.distinct_id,
        timestamp=event.timestamp,
        properties=event.properties,
        status=RawEventStatus.pending.value,
    )
    await connection.execute(stmt)
