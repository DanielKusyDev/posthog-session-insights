from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import RawEvent, Session, EnrichedEventCreate, RawEventStatus
from test.helpers import AsyncContextManagerMock


@pytest.fixture
def mock_connection() -> AsyncMock:
    """Mock AsyncConnection with properly configured async context manager"""
    conn = AsyncMock(spec=AsyncConnection)

    # Make begin() return our async context manager
    conn.begin = lambda: AsyncContextManagerMock(return_value=conn)

    return conn


@pytest.fixture
def sample_raw_event() -> RawEvent:
    """Sample raw event with valid data"""
    return RawEvent(
        raw_event_id=str(uuid4()),
        event_name="$pageview",
        user_id="user-123",
        timestamp=datetime.utcnow(),
        properties={
            "$session_id": "session-456",
            "$pathname": "/home",
            "title": "Home Page",
        },
        status=RawEventStatus.pending,
        elements_chain=None,
    )


@pytest.fixture
def sample_session() -> Session:
    """Sample session"""
    return Session(
        session_id="session-456",
        user_id="user-123",
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
        event_count=5,
        page_views_count=2,
        clicks_count=3,
        first_page="/home",
        last_page="/about",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_enriched_event() -> EnrichedEventCreate:
    """Sample enriched event input"""
    return EnrichedEventCreate(
        raw_event_id=uuid4(),
        user_id="user-123",
        session_id="session-456",
        timestamp=datetime.utcnow(),
        event_name="$pageview",
        event_type="pageview",
        action_type="view",
        semantic_label="Viewed home page",
        page_path="/home",
        page_title="Home Page",
        element_type=None,
        element_text=None,
        context={},
        sequence_number=6,
    )


@pytest.fixture(scope="session", autouse=True)
def setup(session_mocker: MockerFixture) -> None:
    session_mocker.patch("app.db.init_db", side_effect=AsyncMock())  # Make sure not to use real db, even by mistake
    session_mocker.patch("app.db.get_engine", side_effect=AsyncMock())
