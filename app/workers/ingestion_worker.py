import asyncio

from sqlalchemy.ext.asyncio import AsyncConnection

from app.db import get_connection, get_transaction
from app.models import RawEvent
from app.repositories.raw_event_repo import fetch_events_for_processing
from app.services.event_services import mark_as_failed, mark_as_processing, mark_as_done
from app.services.session_services import get_or_create_session

BATCH_SIZE = 200
WAIT_TIME = 1


async def process_single_event(connection: AsyncConnection, event: RawEvent) -> None:
    """Process a single raw event through the pipeline"""

    try:
        # Extract session_id from PostHog properties
        session_id = event.session_id
        if not session_id:
            raise ValueError(f"Missing $session_id in raw_event {event.raw_event_id}")

        # Get or create session
        session = await get_or_create_session(connection=connection, event=event)

        # Enrich the event
        # enriched = await enrich_event(raw_event=event, session=session)

        # Save enriched event
        # await create_enriched_event(conn, enriched)

        # Update session activity
        # await update_session_activity(conn, session_id, event, enriched.event_type)

        # Mark raw event as processed
        await mark_as_done(connection, event.raw_event_id)

    except Exception:
        await mark_as_failed(connection=connection, event_id=event.raw_event_id)
        raise


async def process_batch(conn: AsyncConnection) -> int:
    raw_events = await fetch_events_for_processing(conn, batch_size=BATCH_SIZE)
    if not raw_events:
        return 0

    for event in raw_events:
        await process_single_event(conn, event)

    return len(raw_events)


async def main() -> None:
    while True:
        async with get_transaction() as conn:
            processed = await process_batch(conn)

        if processed == 0:
            await asyncio.sleep(WAIT_TIME)


if __name__ == "__main__":
    asyncio.run(main())
