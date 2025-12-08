from datetime import datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db_models import enriched_event, raw_event, session
from app.models import EnrichedEvent, RawEvent, RawEventStatus, Session


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


async def fetch_recent_events(
    connection: AsyncConnection, user_id: str, limit: int = 20, lookback_hours: int | None = None
) -> list[EnrichedEvent]:
    """Fetch recent enriched events for a user."""
    stmt = select(enriched_event).where(enriched_event.c.user_id == user_id).order_by(desc(enriched_event.c.timestamp))
    if limit:
        stmt = stmt.limit(limit)

    # Optional time filter
    if lookback_hours:
        since = datetime.utcnow() - timedelta(hours=lookback_hours)
        stmt = stmt.where(enriched_event.c.timestamp >= since)

    result = await connection.execute(stmt)
    rows = result.fetchall()

    return [EnrichedEvent.model_validate(row) for row in rows]


async def fetch_latest_session(connection: AsyncConnection, user_id: str) -> Session | None:
    """Fetch the most recent session for a user."""
    stmt = select(session).where(session.c.user_id == user_id).order_by(desc(session.c.started_at)).limit(1)

    result = await connection.execute(stmt)
    row = result.fetchone()

    if row:
        return Session.model_validate(row)
    return None


async def fetch_session_events(connection: AsyncConnection, session_id: str) -> list[EnrichedEvent]:
    """Fetch all enriched events for a specific session. Ordered by sequence number for accurate pattern detection."""
    stmt = (
        select(enriched_event)
        .where(enriched_event.c.session_id == session_id)
        .order_by(enriched_event.c.sequence_number)
    )

    result = await connection.execute(stmt)
    rows = result.fetchall()

    return [EnrichedEvent.model_validate(row) for row in rows]


async def fetch_user_sessions(
    connection: AsyncConnection, user_id: str, limit: int = 10, active_only: bool = False
) -> list[Session]:
    """Fetch recent sessions for a user."""
    stmt = select(session).where(session.c.user_id == user_id).order_by(desc(session.c.started_at)).limit(limit)

    if active_only:
        stmt = stmt.where(session.c.is_active == True)

    result = await connection.execute(stmt)
    rows = result.fetchall()

    return [Session.model_validate(row) for row in rows]


async def count_user_events(connection: AsyncConnection, user_id: str, lookback_hours: int | None = None) -> int:
    """Count total events for a user."""
    stmt = select(func.count()).select_from(enriched_event).where(enriched_event.c.user_id == user_id)

    if lookback_hours:
        since = datetime.utcnow() - timedelta(hours=lookback_hours)
        stmt = stmt.where(enriched_event.c.timestamp >= since)

    result = await connection.execute(stmt)
    return result.scalar() or 0


async def fetch_session(connection: AsyncConnection, session_id: str) -> Session | None:
    stmt = select(session).where(session.c.session_id == session_id)
    result = await connection.execute(stmt)
    row = result.fetchone()
    if row:
        return Session.model_validate(row)
    return None
