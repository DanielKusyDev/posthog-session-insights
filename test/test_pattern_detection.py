from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from pytest import param

from app.models import ActionType, EnrichedEvent, EventType, Pattern, SessionContext, Severity
from app.services.pattern_detection import EventFilter, PatternEngine, PatternRule, SessionFilter

SAMPLE_EVENTS = [
    EnrichedEvent(
        enriched_event_id=uuid4(),
        raw_event_id=uuid4(),
        user_id="user-123",
        session_id="session-456",
        timestamp=datetime(2020, 1, 1, 0, 0, 0),
        created_at=datetime(2020, 1, 1, 0, 0, 0),
        event_name="$pageview",
        event_type=EventType.pageview,
        action_type=ActionType.view,
        semantic_label="Viewed home page",
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
        created_at=datetime(2020, 1, 1, 0, 0, 10),
        event_name="product_clicked",
        event_type=EventType.custom,
        action_type=ActionType.click,
        semantic_label="Selected product: Drone",
        page_path="/products",
        page_title="Products",
        sequence_number=2,
    ),
    EnrichedEvent(
        enriched_event_id=uuid4(),
        raw_event_id=uuid4(),
        user_id="user-123",
        session_id="session-456",
        timestamp=datetime(2020, 1, 1, 0, 0, 20),
        created_at=datetime(2020, 1, 1, 0, 0, 20),
        event_name="$rageclick",
        event_type=EventType.click,
        action_type=ActionType.rage_click,
        semantic_label="Rage-clicked checkout button",
        page_path="/checkout",
        page_title="Checkout",
        sequence_number=3,
    ),
]

SAMPLE_SESSION_CONTEXT = SessionContext(
    session_id="session-456",
    user_id="user-123",
    started_at=datetime(2020, 1, 1, 0, 0, 0),
    ended_at=datetime(2020, 1, 1, 0, 0, 5),
    duration=timedelta(seconds=5),
    event_count=10,
    page_views_count=5,
    clicks_count=5,
    first_page="/home",
    last_page="/checkout",
    is_active=False,
)


@pytest.mark.parametrize(
    "filter_kwargs,expected_count",
    [
        param({"event_type": EventType.pageview}, 1, id="filter_by_event_type"),
        param({"action_type": ActionType.rage_click}, 1, id="filter_by_action_type"),
        param({"page_path_prefix": "/prod"}, 1, id="filter_by_page_path_prefix"),
        param({"page_path_equals": "/home"}, 1, id="filter_by_page_path_equals"),
        param({"semantic_contains": "product"}, 1, id="filter_by_semantic_contains_lowercase"),
        param({"semantic_contains": "PRODUCT"}, 1, id="filter_by_semantic_contains_uppercase"),
        param({"semantic_contains": "pRoDuCt"}, 1, id="filter_by_semantic_contains_mixed_case"),
        param({"event_type": EventType.custom, "semantic_contains": "product"}, 1, id="combined_filters"),
        param({"event_type": EventType.navigation}, 0, id="no_matches"),
    ],
)
def test_event_filter_apply(
    filter_kwargs: dict,
    expected_count: int,
) -> None:
    """Test EventFilter.apply() with various filter combinations"""
    event_filter = EventFilter(**filter_kwargs)
    result = event_filter.apply(SAMPLE_EVENTS)
    assert len(result) == expected_count


def test_event_filter_empty_events() -> None:
    """Test EventFilter on empty event list"""
    event_filter = EventFilter(event_type=EventType.pageview)
    result = event_filter.apply([])
    assert result == []


@pytest.mark.parametrize(
    "session_context, filter_kwargs, should_match",
    [
        param(SAMPLE_SESSION_CONTEXT, {"min_duration_seconds": 4}, True, id="min_duration_pass"),
        param(SAMPLE_SESSION_CONTEXT, {"min_duration_seconds": 600}, False, id="min_duration_fail"),
        param(SAMPLE_SESSION_CONTEXT, {"max_duration_seconds": 600}, True, id="max_duration_pass"),
        param(SAMPLE_SESSION_CONTEXT, {"max_duration_seconds": 4}, False, id="max_duration_fail"),
        param(SAMPLE_SESSION_CONTEXT, {"min_events": 5}, True, id="min_events_pass"),
        param(SAMPLE_SESSION_CONTEXT, {"min_events": 20}, False, id="min_events_fail"),
        param(SAMPLE_SESSION_CONTEXT, {"max_events": 20}, True, id="max_events_pass"),
        param(SAMPLE_SESSION_CONTEXT, {"max_events": 5}, False, id="max_events_fail"),
        param(SAMPLE_SESSION_CONTEXT, {"min_page_views": 3}, True, id="min_page_views_pass"),
        param(SAMPLE_SESSION_CONTEXT, {"min_page_views": 6}, False, id="min_page_views_block"),
        param(SAMPLE_SESSION_CONTEXT, {"max_page_views": 10}, True, id="max_page_views_pass"),
        param(SAMPLE_SESSION_CONTEXT, {"max_page_views": 1}, False, id="max_page_views_block"),
        param(SAMPLE_SESSION_CONTEXT, {"min_duration_seconds": 4, "min_events": 5}, True, id="combined_pass"),
        param(SAMPLE_SESSION_CONTEXT, {"min_duration_seconds": 4, "min_events": 20}, False, id="combined_fail"),
        param(
            SessionContext(
                session_id="active",
                user_id="user-123",
                started_at=datetime.utcnow(),
                ended_at=None,
                duration=None,  # Active session
                event_count=5,
                page_views_count=2,
                clicks_count=3,
                is_active=True,
            ),
            {"min_duration_seconds": 60},
            False,
            id="active_session_no_duration",
        ),
        param(
            SessionContext(
                session_id="active",
                user_id="user-123",
                started_at=datetime.utcnow(),
                ended_at=None,
                duration=None,  # Active session
                event_count=5,
                page_views_count=2,
                clicks_count=3,
                is_active=True,
            ),
            {"max_duration_seconds": 60},
            False,
            id="active_session_no_duration",
        ),
    ],
)
def test_session_filter_matches(
    session_context: SessionContext,
    filter_kwargs: dict,
    should_match: bool,
) -> None:
    """Test SessionFilter.matches() with various conditions"""
    session_filter = SessionFilter(**filter_kwargs)
    assert session_filter.matches(session_context) == should_match


@pytest.mark.parametrize(
    "events, session_context, pattern_rule, expected",
    [
        param(
            [],
            SAMPLE_SESSION_CONTEXT,
            PatternRule(
                code="test_pattern",
                description="Test",
                severity=Severity.low,
                filter=EventFilter(event_type=EventType.pageview),
                min_count=1,
            ),
            False,
            id="no_events",
        ),
        param(
            SAMPLE_EVENTS,
            SAMPLE_SESSION_CONTEXT,
            PatternRule(
                code="test_pattern",
                description="Test pattern",
                severity=Severity.low,
                filter=EventFilter(event_type=EventType.pageview),
                min_count=1,
            ),
            True,
            id="event_filter_pass",
        ),
        param(
            SAMPLE_EVENTS,
            SAMPLE_SESSION_CONTEXT,
            PatternRule(
                code="test_pattern",
                description="Test pattern",
                severity=Severity.low,
                filter=EventFilter(event_type=EventType.pageview),
                min_count=5,  # Only 1 pageview in sample_events
            ),
            False,
            id="event_filter_block",
        ),
        param(
            SAMPLE_EVENTS,
            SAMPLE_SESSION_CONTEXT,
            PatternRule(
                code="test_pattern",
                description="Test pattern",
                severity=Severity.low,
                filter=EventFilter(event_type=EventType.pageview),
                min_count=1,
                negative_filter=EventFilter(event_type=EventType.navigation),
            ),
            True,  # Should match (has pageview, no navigation)
            id="negative_filter_pass",
        ),
        param(
            SAMPLE_EVENTS,
            SAMPLE_SESSION_CONTEXT,
            PatternRule(
                code="test_pattern",
                description="Test pattern",
                severity=Severity.low,
                filter=EventFilter(event_type=EventType.custom),
                min_count=1,
                negative_filter=EventFilter(action_type=ActionType.rage_click),
            ),
            False,  # Should not match (has custom event but also has rage click)
            id="negative_filter_block",
        ),
        param(
            SAMPLE_EVENTS,
            SAMPLE_SESSION_CONTEXT,
            PatternRule(
                code="short_session",
                description="Very short session",
                severity=Severity.low,
                session_filter=SessionFilter(max_duration_seconds=600),  # 10 min
            ),
            True,  # Should match (session is 5 minutes)
            id="session_filter_pass",
        ),
        param(
            SAMPLE_EVENTS,
            SAMPLE_SESSION_CONTEXT,
            PatternRule(
                code="long_session",
                description="Long session pattern",
                severity=Severity.low,
                filter=EventFilter(event_type=EventType.pageview),
                min_count=1,
                session_filter=SessionFilter(min_duration_seconds=600),  # 10 min required
            ),
            False,  # Should not match (max session is 5 minutes)
            id="session_filter_block",
        ),
        param(
            [
                EnrichedEvent(
                    enriched_event_id=uuid4(),
                    raw_event_id=uuid4(),
                    user_id="user-123",
                    session_id="session-456",
                    timestamp=datetime(2020, 1, 1),
                    created_at=datetime(2020, 1, 1),
                    event_name="checkout_started",
                    event_type=EventType.custom,
                    semantic_label="Started checkout",
                    sequence_number=1,
                ),
                EnrichedEvent(
                    enriched_event_id=uuid4(),
                    raw_event_id=uuid4(),
                    user_id="user-123",
                    session_id="session-456",
                    timestamp=datetime(2020, 1, 1, 0, 40),  # 40 min later
                    created_at=datetime(2020, 1, 1, 0, 40),
                    event_name="order_completed",
                    event_type=EventType.custom,
                    semantic_label="Order completed",
                    sequence_number=2,
                ),
            ],
            SessionContext(
                session_id="session-456",
                user_id="user-123",
                started_at=datetime(2020, 1, 1),
                ended_at=datetime(2020, 1, 1, 0, 45),
                duration=timedelta(minutes=45),
                event_count=2,
                page_views_count=0,
                clicks_count=0,
                is_active=False,
            ),
            PatternRule(
                code="checkout_abandoned",
                description="Checkout abandoned",
                severity=Severity.high,
                filter=EventFilter(semantic_contains="checkout"),
                min_count=1,
                negative_filter=EventFilter(semantic_contains="completed"),
                negative_time_window=timedelta(minutes=30),
            ),
            True,  # Should match (completion was AFTER 30-min window)
            id="negative_filter_time_window_pass",
        ),
        param(
            [
                EnrichedEvent(
                    enriched_event_id=uuid4(),
                    raw_event_id=uuid4(),
                    user_id="user-123",
                    session_id="session-456",
                    timestamp=datetime(2020, 1, 1),
                    created_at=datetime(2020, 1, 1),
                    event_name="checkout_started",
                    event_type=EventType.custom,
                    semantic_label="Started checkout",
                    sequence_number=1,
                ),
                EnrichedEvent(
                    enriched_event_id=uuid4(),
                    raw_event_id=uuid4(),
                    user_id="user-123",
                    session_id="session-456",
                    timestamp=datetime(2020, 1, 1, 0, 40),  # 40 min later
                    created_at=datetime(2020, 1, 1, 0, 40),
                    event_name="order_completed",
                    event_type=EventType.custom,
                    semantic_label="Order completed",
                    sequence_number=2,
                ),
            ],
            SessionContext(
                session_id="session-456",
                user_id="user-123",
                started_at=datetime(2020, 1, 1),
                ended_at=datetime(2020, 1, 1, 0, 45),
                duration=timedelta(minutes=45),
                event_count=2,
                page_views_count=0,
                clicks_count=0,
                is_active=False,
            ),
            PatternRule(
                code="checkout_abandoned",
                description="Checkout abandoned",
                severity=Severity.high,
                filter=EventFilter(semantic_contains="checkout"),
                min_count=1,
                negative_filter=EventFilter(semantic_contains="completed"),
                negative_time_window=timedelta(minutes=45),
            ),
            False,  # Should not match (event found in exactly 45 minutes since last one)
            id="negative_filter_time_window_block",
        ),
    ],
)
def test_pattern_rule_match(
    events: list[EnrichedEvent], session_context: SessionContext, pattern_rule: PatternRule, expected: bool
) -> None:
    assert pattern_rule.matches(events, session_context) == expected


@pytest.mark.parametrize(
    "rules, expected_detected_codes",
    [
        param(
            [
                PatternRule(
                    code="pageview_pattern",
                    description="Has pageview",
                    severity=Severity.low,
                    filter=EventFilter(event_type=EventType.pageview),
                    min_count=1,
                ),
                PatternRule(
                    code="rage_click_pattern",
                    description="Has rage click",
                    severity=Severity.high,
                    filter=EventFilter(action_type=ActionType.rage_click),
                    min_count=1,
                ),
            ],
            ["pageview_pattern", "rage_click_pattern"],
            id="two_patterns_detected",
        ),
        param(
            [
                PatternRule(
                    code="impossible_pattern",
                    description="Impossible to match",
                    severity=Severity.low,
                    filter=EventFilter(event_type=EventType.navigation),
                    min_count=10,  # Way too many
                ),
            ],
            [],
            id="no_pattern_detected",
        ),
    ],
)
def test_pattern_engine_detects_matching_patterns(
    rules: list[PatternRule],
    expected_detected_codes: list[str],
) -> None:
    """Test PatternEngine detects matching patterns"""

    engine = PatternEngine(rules)
    patterns = engine.detect(SAMPLE_EVENTS, SAMPLE_SESSION_CONTEXT)
    assert sorted(p.code for p in patterns) == sorted(expected_detected_codes)


def test_pattern_to_pattern_conversion() -> None:
    """Test PatternRule.to_pattern() creates proper Pattern object"""
    rule = PatternRule(
        code="test_code",
        description="Test description",
        severity=Severity.high,
        filter=EventFilter(event_type=EventType.pageview),
    )

    pattern = rule.to_pattern()

    assert isinstance(pattern, Pattern)
    assert pattern.code == "test_code"
    assert pattern.description == "Test description"
    assert pattern.severity == Severity.high
