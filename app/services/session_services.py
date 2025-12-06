from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import RawEvent, SessionCreate
from app.repositories.session_repo import fetch_session, create_session


async def get_or_create_session(connection: AsyncConnection, event: RawEvent):
    session = await fetch_session(connection=connection, session_id=event.session_id)

    if not session:
        new_session = SessionCreate(
            session_id=event.session_id,
            user_id=event.user_id,
            started_at=event.timestamp,
            last_activity_at=event.timestamp,
            first_page=event.page_path,
            is_active=True,
        )
        session = await create_session(connection=connection, input_data=new_session)
    return session
