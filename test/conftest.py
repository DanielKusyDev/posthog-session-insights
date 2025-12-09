from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.testclient import TestClient

from app.api.dependencies import get_transaction_dependency
from app.api.routes import router
from app.models import EnrichedEventCreate
from test.helpers import AsyncContextManagerMock


@pytest.fixture
def mock_connection() -> AsyncMock:
    """Mock AsyncConnection with properly configured async context manager"""
    conn = AsyncMock(spec=AsyncConnection)

    # Make begin() return our async context manager
    conn.begin = lambda: AsyncContextManagerMock(return_value=conn)

    return conn


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


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client"""

    async def override_get_transaction():
        mock_conn = AsyncMock()
        yield mock_conn

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_transaction_dependency] = override_get_transaction

    # Create test client (synchronous!)
    return TestClient(app)
