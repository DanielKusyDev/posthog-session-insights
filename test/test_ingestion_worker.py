from datetime import datetime
from test.helpers import AsyncContextManagerMock
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from app.models import EnrichedEventCreate, RawEvent, RawEventStatus, Session
from app.workers.ingestion_worker import process_batch, process_single_event, process_with_semaphore

SAMPLE_RAW_EVENT = RawEvent(
    raw_event_id=str(uuid4()),
    event_name="$pageview",
    user_id="user-123",
    timestamp=datetime(2020, 1, 1),
    properties={
        "$session_id": "session-456",
        "$pathname": "/home",
        "title": "Home Page",
    },
    status=RawEventStatus.pending,
    elements_chain=None,
)

SAMPLE_SESSION = Session(
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

SAMPLE_ENRICHED_EVENT = EnrichedEventCreate(
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


@pytest.fixture
def mock_main_transaction(mocker: MockerFixture) -> None:
    mocker.patch("app.workers.ingestion_worker.get_transaction", new=lambda: AsyncContextManagerMock())


@pytest.mark.asyncio
async def test_process_single_event_success(mocker: MockerFixture, mock_connection: AsyncMock) -> None:
    """Test successful processing of a single event"""

    mock_get_session = mocker.patch("app.workers.ingestion_worker.get_or_create_session", return_value=SAMPLE_SESSION)
    mock_enrich = mocker.patch("app.workers.ingestion_worker.enrich_event", return_value=SAMPLE_ENRICHED_EVENT)
    mock_create = mocker.patch("app.workers.ingestion_worker.create_enriched_event")
    mock_update = mocker.patch("app.workers.ingestion_worker.update_session_activity")
    mock_mark_done = mocker.patch("app.workers.ingestion_worker.mark_event_as_done")

    await process_single_event(mock_connection, SAMPLE_RAW_EVENT)

    mock_get_session.assert_awaited_once_with(connection=mock_connection, event=SAMPLE_RAW_EVENT)
    mock_enrich.assert_awaited_once_with(event=SAMPLE_RAW_EVENT, session=SAMPLE_SESSION)
    mock_create.assert_awaited_once_with(connection=mock_connection, input_data=SAMPLE_ENRICHED_EVENT)
    mock_update.assert_awaited_once()
    mock_mark_done.assert_awaited_once_with(connection=mock_connection, event_id=SAMPLE_RAW_EVENT.raw_event_id)


@pytest.mark.asyncio
async def test_process_single_event_missing_session_id(mock_connection: AsyncMock) -> None:
    """Test handling of event without session_id"""
    event = RawEvent(
        raw_event_id=str(uuid4()),
        event_name="$pageview",
        user_id="user-123",
        timestamp=datetime(2020, 1, 1),
        properties={},
        status=RawEventStatus.pending,
    )
    with pytest.raises(ValueError):
        await process_single_event(mock_connection, event)


@pytest.mark.asyncio
async def test_process_single_event_enrichment_fails(mocker: MockerFixture, mock_connection: AsyncMock) -> None:
    """Test handling when enrichment fails"""

    mocker.patch("app.workers.ingestion_worker.get_or_create_session", return_value=SAMPLE_SESSION)
    mocker.patch("app.workers.ingestion_worker.enrich_event", side_effect=Exception())

    with pytest.raises(Exception):
        await process_single_event(mock_connection, SAMPLE_RAW_EVENT)


@pytest.mark.asyncio
async def test_process_with_semaphore_success(mocker: MockerFixture) -> None:
    """Test successful processing with semaphore"""

    mocker.patch("app.workers.ingestion_worker.get_connection", new=lambda: AsyncContextManagerMock())
    mock_process = mocker.patch("app.workers.ingestion_worker.process_single_event")
    mock_mark_failed = mocker.patch("app.workers.ingestion_worker.mark_event_as_failed")

    await process_with_semaphore(SAMPLE_RAW_EVENT)

    mock_process.assert_awaited_once()
    mock_mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_with_semaphore_failure_marks_as_failed(mocker: MockerFixture) -> None:
    """Test that failed events are marked as failed"""
    conn_begin = MagicMock()
    mocker.patch(
        "app.workers.ingestion_worker.get_connection",
        new=lambda: AsyncContextManagerMock(return_value=conn_begin),
    )
    mocker.patch("app.workers.ingestion_worker.process_single_event", side_effect=Exception())
    mock_mark_failed = mocker.patch("app.workers.ingestion_worker.mark_event_as_failed")

    await process_with_semaphore(SAMPLE_RAW_EVENT)

    mock_mark_failed.assert_awaited_once_with(conn_begin, SAMPLE_RAW_EVENT.raw_event_id)


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_main_transaction")
async def test_process_batch_with_events(mocker: MockerFixture) -> None:
    """Test processing a batch of events"""

    events = [SAMPLE_RAW_EVENT for _ in range(3)]

    # Setup mocks
    mocker.patch("app.workers.ingestion_worker.fetch_events_for_processing", return_value=events)
    mock_process = mocker.patch("app.workers.ingestion_worker.process_with_semaphore")

    # Execute
    result = await process_batch()

    # Verify
    assert result == 3
    assert mock_process.await_count == 3


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_main_transaction")
async def test_process_batch_empty(mocker: MockerFixture) -> None:
    """Test processing when no events are available"""
    mocker.patch("app.workers.ingestion_worker.fetch_events_for_processing", return_value=[])
    assert await process_batch() == 0


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_main_transaction")
async def test_process_batch_partial_failure(mocker: MockerFixture) -> None:
    """Test that batch continues processing even if some events fail"""

    events = [SAMPLE_RAW_EVENT for _ in range(5)]

    # Mock get_transaction
    mocker.patch("app.workers.ingestion_worker.fetch_events_for_processing", return_value=events)

    # Track which events were processed
    processed_events = []
    failed_events = []

    # Mock process_with_semaphore to simulate partial failure
    async def mock_process(event: RawEvent) -> None:
        processed_events.append(event.raw_event_id)

        # Simulate failure for second event
        if len(processed_events) == 2:
            failed_events.append(event.raw_event_id)
            # Real function catches exception and doesn't re-raise!
            return

    mocker.patch("app.workers.ingestion_worker.process_with_semaphore", side_effect=mock_process)

    # Execute - should complete all 5 without raising
    result = await process_batch()

    # Verify all were attempted
    assert result == 5
    assert len(processed_events) == 5
    assert len(failed_events) == 1  # One failed


@pytest.mark.asyncio
async def test_full_event_processing_flow(mocker: MockerFixture, mock_connection: AsyncMock) -> None:
    """Integration test for full event processing flow"""

    mock_session = mocker.patch("app.workers.ingestion_worker.get_or_create_session", return_value=SAMPLE_SESSION)
    mock_enrich = mocker.patch("app.workers.ingestion_worker.enrich_event", return_value=SAMPLE_ENRICHED_EVENT)
    mock_create = mocker.patch("app.workers.ingestion_worker.create_enriched_event")
    mock_update = mocker.patch("app.workers.ingestion_worker.update_session_activity")
    mock_mark_done = mocker.patch("app.workers.ingestion_worker.mark_event_as_done")

    await process_single_event(mock_connection, SAMPLE_RAW_EVENT)

    assert mock_session.await_count == 1
    assert mock_enrich.await_count == 1
    assert mock_create.await_count == 1
    assert mock_update.await_count == 1
    assert mock_mark_done.await_count == 1
