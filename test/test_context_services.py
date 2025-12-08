from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pytest import mark, param

from app.models import RawEvent, ActionType, EventType, EnrichedEvent
from app.services.context_services import build_context, generate_events_summary
from app.services.event_parsing import ParsedElements


@mark.parametrize(
    "event_properties,element_info,event_name,expected",
    [
        # Basic case - catch-all non-$ properties
        param(
            {"product_id": "3", "product_name": "FPV Speedster"},
            ParsedElements(),
            "product_clicked",
            {
                "product_id": "3",
                "product_name": "FPV Speedster",
                "posthog_event": "product_clicked",
            },
            id="basic_custom_properties",
        ),
        # Filter out $ properties
        param(
            {"$pathname": "/about", "title": "About Us"},
            ParsedElements(),
            "$pageview",
            {"title": "About Us", "posthog_event": "$pageview"},
            id="filter_dollar_properties",
        ),
        # Filter out excluded keys
        param(
            {"token": "secret", "distinct_id": "123", "user_role": "admin"},
            ParsedElements(),
            "custom_event",
            {"user_role": "admin", "posthog_event": "custom_event"},
            id="filter_excluded_keys",
        ),
        # Element attributes with hyphen conversion
        param(
            {},
            ParsedElements(attributes={"product-id": "3", "product-name": "Drone"}),
            "click",
            {
                "product_id": "3",
                "product_name": "Drone",
                "posthog_event": "click",
            },
            id="element_attributes_hyphen_conversion",
        ),
        # Hierarchy included
        param(
            {},
            ParsedElements(hierarchy=["button", "nav", "header", "body", "html"]),
            "click",
            {
                "hierarchy": ["button", "nav", "header", "body", "html"],
                "posthog_event": "click",
            },
            id="hierarchy_all_levels",
        ),
        # Combined - properties + attributes + hierarchy
        param(
            {"user_role": "admin", "$time": 123456},
            ParsedElements(
                attributes={"nav": "home", "form-id": "contact"},
                hierarchy=["button", "form"],
            ),
            "$autocapture",
            {
                "user_role": "admin",
                "nav": "home",
                "form_id": "contact",
                "hierarchy": ["button", "form"],
                "posthog_event": "$autocapture",
            },
            id="combined_all",
        ),
        # Empty case
        param(
            {},
            ParsedElements(),
            None,
            {"posthog_event": "test"},
            id="empty_everything",
        ),
        # All excluded
        param(
            {"$lib": "web", "$session_id": "123", "token": "abc"},
            ParsedElements(),
            "test",
            {"posthog_event": "test"},
            id="all_properties_excluded",
        ),
    ],
)
@mark.asyncio
async def test_build_context(
    event_properties: dict,
    element_info: ParsedElements,
    event_name: str | None,
    expected: dict,
) -> None:
    """Test context building from event properties and element info"""
    # Create mock RawEvent
    raw_event = RawEvent(
        raw_event_id=UUID("12345678123456781234567812345678"),
        event_name=event_name or "test",
        user_id="user-123",
        timestamp="2025-01-01T00:00:00Z",
        properties=event_properties,
        status="PENDING",
    )

    result = await build_context(raw_event.event_name, raw_event.properties, element_info)
    assert result == expected


@mark.asyncio
async def test_build_context_attribute_override() -> None:
    """Test that element attributes override properties with same key"""
    raw_event = RawEvent(
        raw_event_id=UUID("12345678123456781234567812345678"),
        event_name="click",
        user_id="user-123",
        timestamp="2025-01-01T00:00:00Z",
        properties={"product_id": "old"},
        status="PENDING",
    )

    element_info = ParsedElements(attributes={"product-id": "new"})
    result = await build_context(raw_event.event_name, raw_event.properties, element_info)

    # Element attribute should override property
    assert result["product_id"] == "new"


@pytest.mark.parametrize(
    "events,expected_summary",
    [
        pytest.param(
            [],
            "No activity recorded",
            id="empty_events",
        ),
        pytest.param(
            [
                EnrichedEvent(
                    enriched_event_id=uuid4(),
                    raw_event_id=uuid4(),
                    user_id="u1",
                    session_id="s1",
                    timestamp=datetime.utcnow(),
                    event_name="$pageview",
                    event_type=EventType.pageview,
                    semantic_label="Viewed home",
                    action_type=ActionType.view,
                    page_title="Home",
                    sequence_number=1,
                )
            ],
            "Viewed 1 page",
            id="single_pageview_no_clicks",
        ),
        pytest.param(
            [
                EnrichedEvent(
                    enriched_event_id=uuid4(),
                    raw_event_id=uuid4(),
                    user_id="u1",
                    session_id="s1",
                    timestamp=datetime.utcnow(),
                    event_name="$autocapture",
                    event_type=EventType.click,
                    semantic_label="Clicked",
                    action_type=ActionType.click,
                    sequence_number=1,
                )
            ],
            "Clicked 1 time",
            id="single_click_no_pageviews",
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_events_summary_basic_cases(
    events: list[EnrichedEvent],
    expected_summary: str,
) -> None:
    """Test generate_events_summary with basic event combinations"""

    summary = await generate_events_summary(events)

    assert expected_summary in summary


@pytest.mark.asyncio
async def test_generate_events_summary_multiple_pageviews() -> None:
    """Test summary with multiple pageviews"""

    events = [
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="$pageview",
            event_type=EventType.pageview,
            semantic_label="Viewed",
            action_type=ActionType.view,
            page_title="Home",
            sequence_number=1,
        ),
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="$pageview",
            event_type=EventType.pageview,
            semantic_label="Viewed",
            action_type=ActionType.view,
            page_title="Products",
            sequence_number=2,
        ),
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="$pageview",
            event_type=EventType.pageview,
            semantic_label="Viewed",
            action_type=ActionType.view,
            page_title="Checkout",
            sequence_number=3,
        ),
    ]

    summary = await generate_events_summary(events)

    assert "Viewed 3 pages" in summary
    assert "Home" in summary
    assert "Products" in summary
    assert "Checkout" in summary


@pytest.mark.asyncio
async def test_generate_events_summary_limits_pages_to_three() -> None:
    """Test that summary shows max 3 page titles"""

    events = [
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="$pageview",
            event_type=EventType.pageview,
            semantic_label="Viewed",
            action_type=ActionType.view,
            page_title=f"Page {i}",
            sequence_number=i,
        )
        for i in range(1, 6)  # 5 pages
    ]

    summary = await generate_events_summary(events)

    assert "Viewed 5 pages" in summary
    # Should show only first 3
    assert "Page 1" in summary
    assert "Page 2" in summary
    assert "Page 3" in summary
    # Should NOT show 4 and 5
    assert "Page 4" not in summary
    assert "Page 5" not in summary


@pytest.mark.asyncio
async def test_generate_events_summary_deduplicates_page_titles() -> None:
    """Test that duplicate page titles are shown once"""

    events = [
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="$pageview",
            event_type=EventType.pageview,
            semantic_label="Viewed",
            action_type=ActionType.view,
            page_title="Home",
            sequence_number=1,
        ),
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="$pageview",
            event_type=EventType.pageview,
            semantic_label="Viewed",
            action_type=ActionType.view,
            page_title="Home",  # Duplicate
            sequence_number=2,
        ),
    ]

    summary = await generate_events_summary(events)

    assert "Viewed 2 pages" in summary
    # Should mention "Home" only once
    assert summary.count("Home") == 1


@pytest.mark.asyncio
async def test_generate_events_summary_with_rage_clicks() -> None:
    """Test summary includes rage click detection"""

    events = [
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="$rageclick",
            event_type=EventType.click,
            semantic_label="Rage clicked",
            action_type=ActionType.rage_click,
            sequence_number=1,
        ),
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="$rageclick",
            event_type=EventType.click,
            semantic_label="Rage clicked",
            action_type=ActionType.rage_click,
            sequence_number=2,
        ),
    ]

    summary = await generate_events_summary(events)

    assert "Rage-clicked 2 times" in summary
    assert "frustration detected" in summary


@pytest.mark.asyncio
async def test_generate_events_summary_with_custom_events() -> None:
    """Test summary includes custom events count"""

    events = [
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="product_added",
            event_type=EventType.custom,
            semantic_label="Added product",
            sequence_number=1,
        ),
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="checkout_started",
            event_type=EventType.custom,
            semantic_label="Started checkout",
            sequence_number=2,
        ),
    ]

    summary = await generate_events_summary(events)

    assert "Triggered 2 custom events" in summary


@pytest.mark.asyncio
async def test_generate_events_summary_complete_session() -> None:
    """Test summary with all event types"""

    events = [
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="$pageview",
            event_type=EventType.pageview,
            semantic_label="Viewed",
            action_type=ActionType.view,
            page_title="Home",
            sequence_number=1,
        ),
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="$pageview",
            event_type=EventType.pageview,
            semantic_label="Viewed",
            action_type=ActionType.view,
            page_title="Products",
            sequence_number=2,
        ),
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="$autocapture",
            event_type=EventType.click,
            semantic_label="Clicked",
            action_type=ActionType.click,
            sequence_number=3,
        ),
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="$rageclick",
            event_type=EventType.click,
            semantic_label="Rage clicked",
            action_type=ActionType.rage_click,
            sequence_number=4,
        ),
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="product_added",
            event_type=EventType.custom,
            semantic_label="Added product",
            sequence_number=5,
        ),
    ]

    summary = await generate_events_summary(events)

    # All parts should be present
    assert "Viewed 2 pages" in summary
    assert "Home" in summary
    assert "Products" in summary
    assert "Clicked 2 times" in summary  # Regular click + rage click
    assert "Rage-clicked 1 time" in summary
    assert "Triggered 1 custom event" in summary


@pytest.mark.asyncio
async def test_generate_events_summary_no_significant_activity() -> None:
    """Test summary when no significant events"""

    # Events with no standard types
    events = [
        EnrichedEvent(
            enriched_event_id=uuid4(),
            raw_event_id=uuid4(),
            user_id="u1",
            session_id="s1",
            timestamp=datetime.utcnow(),
            event_name="unknown",
            event_type=EventType.unknown,
            semantic_label="Unknown",
            sequence_number=1,
        ),
    ]

    summary = await generate_events_summary(events)

    assert summary == "No significant activity."


@pytest.mark.asyncio
async def test_generate_events_summary_ends_with_period() -> None:
    """Test that summary always ends with a period"""

    test_cases = [
        [
            EnrichedEvent(
                enriched_event_id=uuid4(),
                raw_event_id=uuid4(),
                user_id="u1",
                session_id="s1",
                timestamp=datetime.utcnow(),
                event_name="$pageview",
                event_type=EventType.pageview,
                semantic_label="Viewed",
                action_type=ActionType.view,
                page_title="Home",
                sequence_number=1,
            )
        ],
        [
            EnrichedEvent(
                enriched_event_id=uuid4(),
                raw_event_id=uuid4(),
                user_id="u1",
                session_id="s1",
                timestamp=datetime.utcnow(),
                event_name="custom",
                event_type=EventType.custom,
                semantic_label="Custom",
                sequence_number=1,
            )
        ],
    ]

    for events in test_cases:
        summary = await generate_events_summary(events)
        assert summary.endswith(".")
