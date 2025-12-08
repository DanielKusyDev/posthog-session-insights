from typing import Any
from uuid import UUID

from app.models import PostHogProperties
from app.services.event_parsing import ParsedElements
from app.utils import hyphens_to_snake_case
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection
from app.db_models import raw_event, RawEventStatus
from app.models import PostHogEvent, RawEvent, RawEventUpdate

CONTEXT_EXCLUDE_KEYS: set[str] = {
    "$lib",
    "$lib_version",
    "token",
    "distinct_id",
    "$pageview_id",
    "$session_id",
    "$time",
}


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
    input_data = RawEventUpdate(status=RawEventStatus.done.value)
    await update_raw_event_status(connection, raw_event_id=event_id, status=RawEventStatus.done)


async def build_context(event_name: str, properties: PostHogProperties, element_info: ParsedElements) -> dict[str, Any]:
    """
    Build context dict with additional metadata for LLM.

    Extracts useful metadata from properties and element info while
    filtering out PostHog internal fields.
    """
    # Skip blacklisted PostHog properties
    context = {
        key: value for key, value in properties.items() if not key.startswith("$") and key not in CONTEXT_EXCLUDE_KEYS
    }

    # Add custom attributes from elements_chain
    for attr_name, attr_value in element_info.attributes.items():
        context[hyphens_to_snake_case(attr_name)] = attr_value  # more python friendly

    # Add element hierarchy
    if element_info.hierarchy:
        context["hierarchy"] = element_info.hierarchy

    # 4. Add original event name (debugging)
    if event_name:
        context["posthog_event"] = event_name

    return context
