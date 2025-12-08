from fastapi import APIRouter
from starlette import status
from starlette.responses import Response

from app.api.dependencies import DbTransaction
from app.config import PATTERN_RULES
from app.models import PostHogEvent, SessionContext, UserContext
from app.services.context_services import generate_events_summary
from app.services.pattern_detection import PatternEngine
from app.services.persist_services import insert_raw_event
from app.services.query_services import fetch_latest_session, fetch_recent_events, fetch_session_events

router = APIRouter()


@router.post("/ingest")
async def ingest(input_data: PostHogEvent, db: DbTransaction) -> Response:
    await insert_raw_event(connection=db, event=input_data)
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.get("/session/context/{user_id}", response_model=UserContext)
async def get_context(db: DbTransaction, user_id: str) -> UserContext:
    cross_session_recent_events = await fetch_recent_events(connection=db, user_id=user_id)
    latest_session = await fetch_latest_session(connection=db, user_id=user_id)

    if not latest_session:
        return UserContext(
            user_id=user_id, recent_events=cross_session_recent_events, last_session_summary=None, patterns=[]
        )

    session_events = await fetch_session_events(connection=db, session_id=latest_session.session_id)
    session_summary = await generate_events_summary(events=session_events)
    session_context = SessionContext(
        session_id=latest_session.session_id,
        user_id=latest_session.user_id,
        started_at=latest_session.started_at,
        ended_at=latest_session.ended_at,
        duration=(latest_session.ended_at - latest_session.started_at if latest_session.ended_at else None),
        event_count=latest_session.event_count,
        page_views_count=latest_session.page_views_count,
        clicks_count=latest_session.clicks_count,
        first_page=latest_session.first_page,
        last_page=latest_session.last_page,
        is_active=latest_session.is_active,
    )
    pattern_engine = PatternEngine(PATTERN_RULES)
    patterns = pattern_engine.detect(session_events, session_context)
    return UserContext(
        user_id=user_id,
        recent_events=cross_session_recent_events,
        last_session_summary=session_summary,
        patterns=patterns,
    )
