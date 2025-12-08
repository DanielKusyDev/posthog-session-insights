# test/test_enrichment_services.py

from datetime import datetime
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from app.models import (
    RawEvent,
    RawEventStatus,
    Session,
    EnrichedEvent,
    EventType,
    ActionType,
    ParsedElements,
    EventClassification,
    PageInfo,
    EnrichedEventCreate,
)
from app.services.enrichment_services import enrich_event

SAMPLE_SESSION = Session(
    session_id="session-456",
    user_id="user-123",
    started_at=datetime(2020, 1, 1),
    last_activity_at=datetime(2020, 1, 1),
    event_count=5,
    page_views_count=2,
    clicks_count=3,
    first_page="/home",
    last_page="/products",
    is_active=True,
    created_at=datetime(2020, 1, 1),
    updated_at=datetime(2020, 1, 1),
)

SAMPLE_RAW_EVENT = RawEvent(
    raw_event_id=uuid4(),
    event_name="$pageview",
    user_id="user-123",
    timestamp=datetime(2020, 1, 1, 12, 0, 0),
    properties={"$pathname": "/home", "title": "Home"},
    status=RawEventStatus.pending,
    elements_chain=None,
)


@pytest.mark.parametrize(
    "parsed_elements,classification,page_info,semantic_label,context,expected",
    [
        pytest.param(
            ParsedElements(element_type="button", element_text="Click Me"),
            EventClassification(event_type=EventType.click, action_type=ActionType.click),
            PageInfo(page_path="/products", page_title="Products"),
            "Clicked 'Click Me' button on products page",
            {"product_id": "123"},
            EnrichedEventCreate(
                raw_event_id=SAMPLE_RAW_EVENT.raw_event_id,
                user_id="user-123",
                session_id="session-456",
                timestamp=datetime(2020, 1, 1, 12, 0, 0),
                event_name="$pageview",
                event_type=EventType.click,
                action_type=ActionType.click,
                semantic_label="Clicked 'Click Me' button on products page",
                page_path="/products",
                page_title="Products",
                element_type="button",
                element_text="Click Me",
                context={"product_id": "123"},
                sequence_number=6,
            ),
            id="click_button_with_context",
        ),
        pytest.param(
            ParsedElements(element_type=None, element_text=None),
            EventClassification(event_type=EventType.pageview, action_type=ActionType.view),
            PageInfo(page_path="/home", page_title="Home Page"),
            "Viewed home page",
            {},
            EnrichedEventCreate(
                raw_event_id=SAMPLE_RAW_EVENT.raw_event_id,
                user_id="user-123",
                session_id="session-456",
                timestamp=datetime(2020, 1, 1, 12, 0, 0),
                event_name="$pageview",
                event_type=EventType.pageview,
                action_type=ActionType.view,
                semantic_label="Viewed home page",
                page_path="/home",
                page_title="Home Page",
                element_type=None,
                element_text=None,
                context={},
                sequence_number=6,
            ),
            id="pageview_no_elements",
        ),
        pytest.param(
            ParsedElements(element_type="link", element_text="Learn More"),
            EventClassification(event_type=EventType.navigation, action_type=ActionType.navigate),
            PageInfo(page_path="/about", page_title="About Us"),
            "Navigated via 'Learn More' link",
            {"hierarchy": ["link", "nav"]},
            EnrichedEventCreate(
                raw_event_id=SAMPLE_RAW_EVENT.raw_event_id,
                user_id="user-123",
                session_id="session-456",
                timestamp=datetime(2020, 1, 1, 12, 0, 0),
                event_name="$pageview",
                event_type=EventType.navigation,
                action_type=ActionType.navigate,
                semantic_label="Navigated via 'Learn More' link",
                page_path="/about",
                page_title="About Us",
                element_type="link",
                element_text="Learn More",
                context={"hierarchy": ["link", "nav"]},
                sequence_number=6,
            ),
            id="navigation_with_hierarchy",
        ),
        pytest.param(
            ParsedElements(),
            EventClassification(event_type=EventType.custom, action_type=ActionType.unknown),
            PageInfo(page_path="/checkout", page_title="Checkout"),
            "Custom event: order_completed",
            {"order_id": "12345", "total": 299.99},
            EnrichedEventCreate(
                raw_event_id=SAMPLE_RAW_EVENT.raw_event_id,
                user_id="user-123",
                session_id="session-456",
                timestamp=datetime(2020, 1, 1, 12, 0, 0),
                event_name="$pageview",
                event_type=EventType.custom,
                action_type=ActionType.unknown,
                semantic_label="Custom event: order_completed",
                page_path="/checkout",
                page_title="Checkout",
                element_type=None,
                element_text=None,
                context={"order_id": "12345", "total": 299.99},
                sequence_number=6,
            ),
            id="custom_event_with_order_data",
        ),
        pytest.param(
            ParsedElements(element_type="button", element_text=None),
            EventClassification(event_type=EventType.click, action_type=ActionType.rage_click),
            PageInfo(page_path="/payment", page_title="Payment"),
            "Rage-clicked button on payment page",
            {},
            EnrichedEventCreate(
                raw_event_id=SAMPLE_RAW_EVENT.raw_event_id,
                user_id="user-123",
                session_id="session-456",
                timestamp=datetime(2020, 1, 1, 12, 0, 0),
                event_name="$pageview",
                event_type=EventType.click,
                action_type=ActionType.rage_click,
                semantic_label="Rage-clicked button on payment page",
                page_path="/payment",
                page_title="Payment",
                element_type="button",
                element_text=None,
                context={},
                sequence_number=6,
            ),
            id="rage_click_no_text",
        ),
    ],
)
@pytest.mark.asyncio
async def test_enrich_event(
    mocker: MockerFixture,
    parsed_elements: ParsedElements,
    classification: EventClassification,
    page_info: PageInfo,
    semantic_label: str,
    context: dict,
    expected: EnrichedEvent,
) -> None:
    """Test enrich_event orchestrates all services correctly"""

    # Mock all services with parametrized values
    mocker.patch(
        "app.services.enrichment_services.parse_elements_chain",
        return_value=parsed_elements,
    )
    mocker.patch(
        "app.services.enrichment_services.classify_event",
        return_value=classification,
    )
    mocker.patch(
        "app.services.enrichment_services.extract_page_info",
        return_value=page_info,
    )
    mocker.patch(
        "app.services.enrichment_services._label_builder.build",
        return_value=semantic_label,
    )
    mocker.patch(
        "app.services.enrichment_services.build_context",
        return_value=context,
    )

    # Execute
    actual = await enrich_event(SAMPLE_RAW_EVENT, SAMPLE_SESSION)

    # Verify entire enriched event matches expected
    assert actual == expected


@pytest.mark.parametrize(
    "session_event_count,expected_sequence",
    [
        pytest.param(0, 1, id="first_event"),
        pytest.param(5, 6, id="sixth_event"),
        pytest.param(99, 100, id="hundredth_event"),
        pytest.param(999, 1000, id="thousandth_event"),
    ],
)
@pytest.mark.asyncio
async def test_enrich_event_sequence_number(
    mocker: MockerFixture,
    session_event_count: int,
    expected_sequence: int,
) -> None:
    """Test sequence number calculation from session event count"""

    # Create session with specific event count
    session = Session(
        session_id="session-456",
        user_id="user-123",
        started_at=datetime(2020, 1, 1),
        last_activity_at=datetime(2020, 1, 1),
        event_count=session_event_count,
        page_views_count=0,
        clicks_count=0,
        is_active=True,
        created_at=datetime(2020, 1, 1),
        updated_at=datetime(2020, 1, 1),
    )

    # Mock services
    mocker.patch(
        "app.services.enrichment_services.parse_elements_chain",
        return_value=ParsedElements(),
    )
    mocker.patch(
        "app.services.enrichment_services.classify_event",
        return_value=EventClassification(event_type=EventType.pageview, action_type=ActionType.view),
    )
    mocker.patch(
        "app.services.enrichment_services.extract_page_info",
        return_value=PageInfo(page_path="/test", page_title="Test"),
    )
    mocker.patch(
        "app.services.enrichment_services._label_builder.build",
        return_value="Label",
    )
    mocker.patch(
        "app.services.enrichment_services.build_context",
        return_value={},
    )

    # Execute
    enriched = await enrich_event(SAMPLE_RAW_EVENT, session)

    # Verify sequence number
    assert enriched.sequence_number == expected_sequence


@pytest.mark.asyncio
async def test_enrich_event_calls_services_with_correct_args(mocker: MockerFixture) -> None:
    """Test that enrich_event calls all services with correct arguments"""

    # Mock all services
    mock_parse = mocker.patch(
        "app.services.enrichment_services.parse_elements_chain",
        return_value=ParsedElements(),
    )
    mock_classify = mocker.patch(
        "app.services.enrichment_services.classify_event",
        return_value=EventClassification(event_type=EventType.pageview, action_type=ActionType.view),
    )
    mock_extract = mocker.patch(
        "app.services.enrichment_services.extract_page_info",
        return_value=PageInfo(page_path="/home", page_title="Home"),
    )
    mock_label = mocker.patch(
        "app.services.enrichment_services._label_builder.build",
        return_value="Label",
    )
    mock_context = mocker.patch(
        "app.services.enrichment_services.build_context",
        return_value={},
    )

    # Execute
    await enrich_event(SAMPLE_RAW_EVENT, SAMPLE_SESSION)

    # Verify service calls with correct arguments
    mock_parse.assert_called_once_with(chain=SAMPLE_RAW_EVENT.elements_chain)
    mock_classify.assert_called_once_with(
        event_name=SAMPLE_RAW_EVENT.event_name,
        properties=SAMPLE_RAW_EVENT.properties,
    )
    mock_extract.assert_called_once_with(properties=SAMPLE_RAW_EVENT.properties)
    mock_label.assert_called_once()
    mock_context.assert_awaited_once()
