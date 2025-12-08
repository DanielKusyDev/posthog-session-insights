from datetime import timedelta

from pydantic import BaseModel

from app.models import EventType, ActionType, EnrichedEvent, Pattern, Severity, SessionContext


class EventFilter(BaseModel):
    event_type: EventType | None = None
    action_type: ActionType | None = None
    page_path_prefix: str | None = None
    page_path_equals: str | None = None
    semantic_contains: str | None = None

    def apply(self, events: list[EnrichedEvent]) -> list[EnrichedEvent]:
        result = events
        if self.event_type is not None:
            result = [e for e in result if e.event_type == self.event_type]
        if self.action_type is not None:
            result = [e for e in result if e.action_type == self.action_type]
        if self.page_path_prefix is not None:
            result = [e for e in result if (e.page_path or "").startswith(self.page_path_prefix)]
        if self.page_path_equals is not None:
            result = [e for e in result if e.page_path == self.page_path_equals]
        if self.semantic_contains is not None:
            result = [e for e in result if self.semantic_contains.lower() in e.semantic_label.lower()]
        return result


class SessionFilter(BaseModel):
    """Filter based on session metadata"""

    min_duration_seconds: float | None = None
    max_duration_seconds: float | None = None
    min_events: int | None = None
    max_events: int | None = None
    min_page_views: int | None = None
    max_page_views: int | None = None

    def matches(self, session: SessionContext) -> bool:
        if self.min_duration_seconds and (session.duration_seconds or 0) < self.min_duration_seconds:
            return False
        if self.max_duration_seconds and (session.duration_seconds or float("inf")) > self.max_duration_seconds:
            return False
        if self.min_events and session.event_count < self.min_events:
            return False
        if self.max_events and session.event_count > self.max_events:
            return False
        if self.min_page_views and session.page_views_count < self.min_page_views:
            return False
        if self.max_page_views and session.page_views_count > self.max_page_views:
            return False
        return True


class PatternRule(BaseModel):
    code: str
    description: str
    severity: Severity

    # Event-based conditions
    filter: EventFilter | None = None
    min_count: int = 1
    negative_filter: EventFilter | None = None
    negative_time_window: timedelta | None = None
    time_window: timedelta | None = None  # Window for checking positive events

    # Session-based conditions
    session_filter: SessionFilter | None = None

    def matches(self, events: list[EnrichedEvent], session: SessionContext) -> bool:
        """Check if pattern matches given events and session context."""
        # Check session filter first (cheaper)
        if self.session_filter and not self.session_filter.matches(session):
            return False

        # If no event filter, only session filter matters
        if self.filter is None:
            return True

        # Sort events by sequence
        events_sorted = sorted(events, key=lambda e: e.sequence_number or 0)

        # Apply positive filter
        positives = self.filter.apply(events_sorted)

        # Check time window for positive events
        if self.time_window:
            positives = self._filter_by_time_window(positives, self.time_window)

        # Check min count
        if len(positives) < self.min_count:
            return False

        # If no negative filter, we're done
        if self.negative_filter is None:
            return True

        # Check negative condition
        negative_candidates = self.negative_filter.apply(events_sorted)

        if self.negative_time_window is None:
            # No negative events at all
            return len(negative_candidates) == 0

        # Check if negative event happened within time window after last positive
        last_pos_time = positives[-1].timestamp
        for e in negative_candidates:
            if last_pos_time <= e.timestamp <= last_pos_time + self.negative_time_window:
                return False  # Found negative event in window

        return True

    def _filter_by_time_window(self, events: list[EnrichedEvent], window: timedelta) -> list[EnrichedEvent]:
        """Keep only events that happened within time window"""
        if not events:
            return []

        # Group events that happened close together
        result = []
        for i, event in enumerate(events):
            if i == 0:
                result.append(event)
                continue

            # Check if within window of any previous event in result
            for prev in result:
                if abs((event.timestamp - prev.timestamp).total_seconds()) <= window.total_seconds():
                    result.append(event)
                    break

        return result

    def to_pattern(self) -> Pattern:
        return Pattern(
            code=self.code,
            description=self.description,
            severity=self.severity,
        )


class PatternEngine:
    def __init__(self, rules: list[PatternRule]) -> None:
        self._rules = rules

    def detect(self, events: list[EnrichedEvent], session: SessionContext) -> list[Pattern]:
        """Detect patterns in events given session context."""
        patterns: list[Pattern] = []
        for rule in self._rules:
            if rule.matches(events, session):
                patterns.append(rule.to_pattern())
        return patterns
