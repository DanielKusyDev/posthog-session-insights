from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from starlette.testclient import TestClient

from app.models import (
    ActionType,
    EnrichedEvent,
    EventType,
    Pattern,
    PostHogEvent,
    Session,
    Severity,
)

SAMPLE_POSTHOG_EVENT = {
    "event": "$pageview",
    "distinct_id": "user-123",
    "properties": {
        "$session_id": "session-456",
        "$pathname": "/home",
        "title": "Home Page",
    },
    "timestamp": datetime.utcnow().isoformat(),
    "elements_chain": None,
}

SAMPLE_ENRICHED_EVENTS = [
    EnrichedEvent(
        enriched_event_id=uuid4(),
        raw_event_id=uuid4(),
        user_id="user-123",
        session_id="session-456",
        timestamp=datetime(2020, 1, 1),
        event_name="$pageview",
        event_type=EventType.pageview,
        semantic_label="Viewed home page",
        action_type=ActionType.view,
        page_path="/home",
        page_title="Home",
        sequence_number=1,
    ),
    EnrichedEvent(
        enriched_event_id=uuid4(),
        raw_event_id=uuid4(),
        user_id="user-123",
        session_id="session-456",
        timestamp=datetime(2020, 1, 1, 0, 0, 10),
        event_name="product_clicked",
        event_type=EventType.custom,
        semantic_label="Clicked product",
        action_type=ActionType.click,
        page_path="/products",
        page_title="Products",
        sequence_number=2,
    ),
]

SAMPLE_SESSION = Session(
    session_id="session-456",
    user_id="user-123",
    started_at=datetime(2020, 1, 1),
    last_activity_at=datetime(2020, 1, 1, 0, 10),
    ended_at=datetime(2020, 1, 1, 0, 10),
    event_count=10,
    page_views_count=5,
    clicks_count=5,
    first_page="/home",
    last_page="/checkout",
    is_active=False,
    created_at=datetime(2020, 1, 1),
    updated_at=datetime(2020, 1, 1, 0, 10),
)


@pytest.mark.asyncio
async def test_ingest_success(mocker: MockerFixture, client: TestClient) -> None:
    mock_insert = mocker.patch("app.api.routes.insert_raw_event", new_callable=AsyncMock)
    response = client.post("/ingest", json={"event": SAMPLE_POSTHOG_EVENT})
    assert response.status_code == 202
    mock_insert.assert_awaited_once()

    call_args = mock_insert.call_args
    event_arg = call_args.kwargs["event"]
    assert isinstance(event_arg, PostHogEvent)
    assert event_arg.event == "$pageview"
    assert event_arg.distinct_id == "user-123"


@pytest.mark.asyncio
async def test_ingest_invalid_payload(client: TestClient) -> None:
    invalid_payload = {"event": "$pageview"}  # Missing required fields
    response = client.post("/ingest", json={"event": invalid_payload})
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload, expected_status",
    [
        pytest.param(
            {
                "distinct_id": "user-123",
                "properties": {},
                "timestamp": datetime.utcnow().isoformat(),
            },
            422,
            id="missing_fields",
        ),
        pytest.param(
            {
                "event": "$pageview",
                "distinct_id": "user-123",
                "properties": {},
                "timestamp": "invalid-timestamp",
                "elements_chain": None,
            },
            422,
            id="invalid_timestamp_format",
        ),
    ],
)
async def test_ingest_error(client: TestClient, payload: dict[str, Any], expected_status: int) -> None:
    """Test ingestion with missing event field"""
    response = client.post("/ingest", json=payload)
    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_get_context_api(mocker: MockerFixture, client: TestClient) -> None:
    """Test getting context for user with existing session"""

    mocker.patch("app.api.routes.fetch_recent_events", new_callable=AsyncMock, return_value=SAMPLE_ENRICHED_EVENTS)
    mocker.patch("app.api.routes.fetch_latest_session", new_callable=AsyncMock, return_value=SAMPLE_SESSION)
    mocker.patch("app.api.routes.fetch_session_events", new_callable=AsyncMock, return_value=SAMPLE_ENRICHED_EVENTS)
    mocker.patch(
        "app.api.routes.generate_events_summary", new_callable=AsyncMock, return_value="Viewed 2 pages. Clicked 1 time."
    )
    mock_pattern = Pattern(code="test_pattern", description="Test pattern detected", severity=Severity.low)
    mock_engine = mocker.MagicMock()
    mock_engine.detect.return_value = [mock_pattern]
    mocker.patch("app.api.routes.PatternEngine", return_value=mock_engine)

    response = client.get("/session/context/user-123")
    assert response.status_code == 200
    data = response.json()

    assert "recent_events" in data
    assert "last_session_summary" in data
    assert "patterns" in data
    assert len(data["recent_events"]) == 2
    assert data["last_session_summary"] == "Viewed 2 pages. Clicked 1 time."
    assert len(data["patterns"]) == 1
    assert data["patterns"][0]["code"] == "test_pattern"


@pytest.mark.asyncio
async def test_get_context_without_session(mocker: MockerFixture, client: TestClient) -> None:
    """Test getting context for user without session"""

    mocker.patch("app.api.routes.fetch_recent_events", new_callable=AsyncMock, return_value=SAMPLE_ENRICHED_EVENTS)
    mocker.patch("app.api.routes.fetch_latest_session", new_callable=AsyncMock, return_value=None)  # No session

    response = client.get("/session/context/user-123")
    assert response.status_code == 200
    data = response.json()

    assert len(data["recent_events"]) == 2
    assert data["last_session_summary"] is None
    assert data["patterns"] == []


@pytest.mark.asyncio
async def test_get_context_empty_recent_events(
    mocker: MockerFixture,
    client: TestClient,
) -> None:
    """Test getting context when user has no events"""

    mocker.patch("app.api.routes.fetch_recent_events", new_callable=AsyncMock, return_value=[])
    mocker.patch("app.api.routes.fetch_latest_session", new_callable=AsyncMock, return_value=None)

    response = client.get("/session/context/user-123")
    assert response.status_code == 200
    data = response.json()

    assert data["recent_events"] == []
    assert data["last_session_summary"] is None
    assert data["patterns"] == []


@pytest.mark.asyncio
async def test_get_context_multiple_patterns(mocker: MockerFixture, client: TestClient) -> None:
    """Test getting context with multiple patterns detected"""
    mocker.patch("app.api.routes.fetch_recent_events", new_callable=AsyncMock, return_value=SAMPLE_ENRICHED_EVENTS)
    mocker.patch("app.api.routes.fetch_latest_session", new_callable=AsyncMock, return_value=SAMPLE_SESSION)
    mocker.patch("app.api.routes.fetch_session_events", new_callable=AsyncMock, return_value=SAMPLE_ENRICHED_EVENTS)
    mocker.patch("app.api.routes.generate_events_summary", new_callable=AsyncMock, return_value="Session summary")
    patterns = [
        Pattern(code="pattern1", description="Pattern 1", severity=Severity.high),
        Pattern(code="pattern2", description="Pattern 2", severity=Severity.medium),
        Pattern(code="pattern3", description="Pattern 3", severity=Severity.low),
    ]
    mock_engine = mocker.MagicMock()
    mock_engine.detect.return_value = patterns
    mocker.patch("app.api.routes.PatternEngine", return_value=mock_engine)

    response = client.get("/session/context/user-123")
    assert response.status_code == 200
    data = response.json()

    assert len(data["patterns"]) == 3
    assert {p["code"] for p in data["patterns"]} == {"pattern1", "pattern2", "pattern3"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_flow_ingest_then_context(mocker: MockerFixture, client: TestClient) -> None:
    """Integration test: ingest event then fetch context"""

    # Mock insert for ingestion
    mocker.patch("app.api.routes.insert_raw_event", new_callable=AsyncMock)

    # Ingest event
    ingest_response = client.post("/ingest", json={"event": SAMPLE_POSTHOG_EVENT})
    assert ingest_response.status_code == 202

    # Mock fetches for context
    mocker.patch("app.api.routes.fetch_recent_events", new_callable=AsyncMock, return_value=SAMPLE_ENRICHED_EVENTS)
    mocker.patch("app.api.routes.fetch_latest_session", new_callable=AsyncMock, return_value=SAMPLE_SESSION)
    mocker.patch("app.api.routes.fetch_session_events", new_callable=AsyncMock, return_value=SAMPLE_ENRICHED_EVENTS)
    mocker.patch("app.api.routes.generate_events_summary", new_callable=AsyncMock, return_value="Summary")

    mock_engine = mocker.MagicMock()
    mock_engine.detect.return_value = []
    mocker.patch("app.api.routes.PatternEngine", return_value=mock_engine)

    # Get context
    context_response = client.get("/session/context/user-123")
    assert context_response.status_code == 200
