import asyncio
import logging
import signal

from sqlalchemy.ext.asyncio import AsyncConnection

from app import init_settings
from app.db import get_connection, get_transaction, init_db
from app.models import RawEvent
from app.services.enrichment_services import enrich_event
from app.services.persist_services import (
    get_or_create_session,
    create_enriched_event,
    update_session_activity,
    mark_event_as_done, mark_event_as_failed,
)
from app.services.query_services import fetch_events_for_processing

BATCH_SIZE = 200
WAIT_TIME = 1

semaphore = asyncio.Semaphore(10)
shutdown_event = asyncio.Event()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


async def process_single_event(connection: AsyncConnection, event: RawEvent) -> None:
    """Process a single raw event through the pipeline"""
    async with connection.begin():
        # Extract session_id from PostHog properties
        session_id = event.session_id
        if not session_id:
            raise ValueError(f"Missing $session_id in raw_event {event.raw_event_id}")

        # Get or create session
        session = await get_or_create_session(connection=connection, event=event)

        # Enrich the event
        enriched_event_data = await enrich_event(event=event, session=session)

        # Save enriched event
        await create_enriched_event(connection=connection, input_data=enriched_event_data)

        # Update session activity
        await update_session_activity(
            connection=connection, session_id=session_id, event=event, enriched_event=enriched_event_data
        )

        # Mark raw event as processed
        await mark_event_as_done(connection=connection, event_id=event.raw_event_id)


async def process_with_semaphore(event_: RawEvent) -> None:
    async with semaphore:
        async with get_connection() as connection:
            try:
                await process_single_event(connection, event_)
            except Exception as e:
                async with connection.begin():
                    await mark_event_as_failed(connection, event_.raw_event_id)
                logger.error(f"Failed to process {event_.raw_event_id}: {e}")


async def process_batch() -> int:
    async with get_transaction() as conn:
        raw_events = await fetch_events_for_processing(conn, batch_size=BATCH_SIZE)

    if not raw_events:
        return 0

    logger.info("Processing %s events...", len(raw_events))
    async with asyncio.TaskGroup() as tg:
        for event in raw_events:
            tg.create_task(process_with_semaphore(event))
    return len(raw_events)


def handle_shutdown(signum, frame):
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    shutdown_event.set()


async def main() -> None:
    init_settings()
    await init_db()

    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    while not shutdown_event.is_set():
        processed = await process_batch()

        if processed == 0:
            logger.info("No jobs to process. Sleeping...")
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=WAIT_TIME)
            except asyncio.TimeoutError:
                pass  # Continue loop

    logger.info("Worker shut down gracefully")


if __name__ == "__main__":
    asyncio.run(main())
