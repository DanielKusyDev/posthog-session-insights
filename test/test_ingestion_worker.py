from typing import AsyncContextManager

import pytest
from pytest_mock import MockerFixture
from unittest.mock import AsyncMock, MagicMock

from app.models import RawEvent, Session, EnrichedEventCreate
from app.workers.ingestion_worker import process_single_event, process_with_semaphore, process_batch
from test.helpers import AsyncContextManagerMock


@pytest.fixture
def mock_main_transaction(mocker: MockerFixture) -> None:
    mocker.patch("app.workers.ingestion_worker.get_transaction", new=lambda: AsyncContextManagerMock())


@pytest.mark.asyncio
async def test_process_single_event_success(
    mocker: MockerFixture,
    mock_connection: AsyncMock,
    sample_raw_event: RawEvent,
    sample_session: Session,
    sample_enriched_event: EnrichedEventCreate,
) -> None:
    """Test successful processing of a single event"""

    mock_get_session = mocker.patch("app.workers.ingestion_worker.get_or_create_session", return_value=sample_session)
    mock_enrich = mocker.patch("app.workers.ingestion_worker.enrich_event", return_value=sample_enriched_event)
    mock_create = mocker.patch("app.workers.ingestion_worker.create_enriched_event")
    mock_update = mocker.patch("app.workers.ingestion_worker.update_session_activity")
    mock_mark_done = mocker.patch("app.workers.ingestion_worker.mark_event_as_done")

    await process_single_event(mock_connection, sample_raw_event)

    mock_get_session.assert_awaited_once_with(connection=mock_connection, event=sample_raw_event)
    mock_enrich.assert_awaited_once_with(event=sample_raw_event, session=sample_session)
    mock_create.assert_awaited_once_with(connection=mock_connection, input_data=sample_enriched_event)
    mock_update.assert_awaited_once()
    mock_mark_done.assert_awaited_once_with(connection=mock_connection, event_id=sample_raw_event.raw_event_id)


@pytest.mark.asyncio
async def test_process_single_event_missing_session_id(mock_connection: AsyncMock, sample_raw_event: RawEvent) -> None:
    """Test handling of event without session_id"""
    sample_raw_event.properties = {}
    with pytest.raises(ValueError):
        await process_single_event(mock_connection, sample_raw_event)


@pytest.mark.asyncio
async def test_process_single_event_enrichment_fails(
    mocker: MockerFixture,
    mock_connection: AsyncMock,
    sample_raw_event: RawEvent,
    sample_session: Session,
) -> None:
    """Test handling when enrichment fails"""

    mocker.patch("app.workers.ingestion_worker.get_or_create_session", return_value=sample_session)
    mocker.patch("app.workers.ingestion_worker.enrich_event", side_effect=Exception())

    with pytest.raises(Exception):
        await process_single_event(mock_connection, sample_raw_event)


@pytest.mark.asyncio
async def test_process_with_semaphore_success(
    mocker: MockerFixture,
    sample_raw_event: RawEvent,
) -> None:
    """Test successful processing with semaphore"""

    mocker.patch("app.workers.ingestion_worker.get_connection", new=lambda: AsyncContextManagerMock())
    mock_process = mocker.patch("app.workers.ingestion_worker.process_single_event")
    mock_mark_failed = mocker.patch("app.workers.ingestion_worker.mark_event_as_failed")

    await process_with_semaphore(sample_raw_event)

    mock_process.assert_awaited_once()
    mock_mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_with_semaphore_failure_marks_as_failed(
    mocker: MockerFixture, sample_raw_event: RawEvent
) -> None:
    """Test that failed events are marked as failed"""
    conn_begin = MagicMock()
    mocker.patch(
        "app.workers.ingestion_worker.get_connection",
        new=lambda: AsyncContextManagerMock(return_value=conn_begin),
    )
    mocker.patch("app.workers.ingestion_worker.process_single_event", side_effect=Exception())
    mock_mark_failed = mocker.patch("app.workers.ingestion_worker.mark_event_as_failed")

    await process_with_semaphore(sample_raw_event)

    mock_mark_failed.assert_awaited_once_with(conn_begin, sample_raw_event.raw_event_id)


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_main_transaction")
async def test_process_batch_with_events(
    mocker: MockerFixture,
    sample_raw_event: RawEvent,
) -> None:
    """Test processing a batch of events"""

    events = [sample_raw_event for _ in range(3)]

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
async def test_process_batch_partial_failure(
    mocker: MockerFixture,
    sample_raw_event: RawEvent,
) -> None:
    """Test that batch continues processing even if some events fail"""

    events = [sample_raw_event for _ in range(5)]

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
async def test_full_event_processing_flow(
    mocker: MockerFixture,
    mock_connection: AsyncMock,
    sample_raw_event: RawEvent,
    sample_session: Session,
    sample_enriched_event: EnrichedEventCreate,
) -> None:
    """Integration test for full event processing flow"""

    mock_session = mocker.patch("app.workers.ingestion_worker.get_or_create_session", return_value=sample_session)
    mock_enrich = mocker.patch("app.workers.ingestion_worker.enrich_event", return_value=sample_enriched_event)
    mock_create = mocker.patch("app.workers.ingestion_worker.create_enriched_event")
    mock_update = mocker.patch("app.workers.ingestion_worker.update_session_activity")
    mock_mark_done = mocker.patch("app.workers.ingestion_worker.mark_event_as_done")

    await process_single_event(mock_connection, sample_raw_event)

    assert mock_session.await_count == 1
    assert mock_enrich.await_count == 1
    assert mock_create.await_count == 1
    assert mock_update.await_count == 1
    assert mock_mark_done.await_count == 1
