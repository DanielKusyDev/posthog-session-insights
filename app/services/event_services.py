from sqlalchemy.ext.asyncio import AsyncConnection

from app.db_models import RawEventStatus
from app.models import RawEventUpdate
from app.repositories.raw_event_repo import update_raw_event


async def mark_as_failed(connection: AsyncConnection, event_id: str) -> None:
    input_data = RawEventUpdate(status=RawEventStatus.failed.value)
    await update_raw_event(connection, raw_event_id=event_id, event=input_data)


async def mark_as_processing(connection: AsyncConnection, event_id: str) -> None:
    input_data = RawEventUpdate(status=RawEventStatus.processing.value)
    await update_raw_event(connection, raw_event_id=event_id, event=input_data)


async def mark_as_done(connection: AsyncConnection, event_id: str) -> None:
    input_data = RawEventUpdate(status=RawEventStatus.done.value)
    await update_raw_event(connection, raw_event_id=event_id, event=input_data)
