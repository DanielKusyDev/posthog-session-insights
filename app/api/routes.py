from fastapi import APIRouter
from pydantic import BaseModel
from starlette import status
from starlette.responses import Response

from app.api.dependencies import DbTransaction
from app.models import PostHogEvent, SessionContext, UserContext
from app.pattern_rules import PATTERN_RULES
from app.services.context_services import generate_events_summary
from app.services.pattern_detection import PatternEngine
from app.services.persist_services import insert_raw_event
from app.services.query_services import fetch_latest_session, fetch_recent_events, fetch_session_events

router = APIRouter()

# For POC purposes only
GET_CONTEXT_DESCRIPTION = """Get user context with recent events, last session summary and patterns.
Important!
To make the demo of this POC easier, I've created a script that automatically sends initial events to the service.
There are 2 pre-created users you can use to see the context results. User IDs:
- 019aff19-86cb-7abd-b27e-5e3a34fc85f2
- 019aff1e-0ace-7a5c-80a8-cfdac2d7e743

You use them in the query to get the initial data quickly, or you can hook the service to your sample data or PostHog
webhook (e.g. through ngrok) and emit your own events.
"""


# PostHog payload format is configurable in their panel but this, single-field format is the simplest
class PostHogWebhookPayload(BaseModel):
    event: PostHogEvent


@router.get("/health")
def health() -> str:
    return "OK"


@router.post("/ingest")
async def ingest(db: DbTransaction, data: PostHogWebhookPayload) -> Response:
    await insert_raw_event(connection=db, event=data.event)
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.get("/session/context/{user_id}", response_model=UserContext, description=GET_CONTEXT_DESCRIPTION)
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
