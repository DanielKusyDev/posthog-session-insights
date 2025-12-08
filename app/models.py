from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel

PostHogProperties = dict[str, Any]
EnrichedContext = dict[str, Any]


class Severity(str, Enum):
    low = "LOW"
    medium = "MEDIUM"
    high = "HIGH"


class RawEventStatus(str, Enum):
    pending = "PENDING"
    done = "DONE"
    failed = "FAILED"


class EventType(str, Enum):
    """High-level event category"""

    pageview = "pageview"
    click = "click"
    navigation = "navigation"
    custom = "custom"
    unknown = "unknown"


class ActionType(str, Enum):
    """Specific user action"""

    view = "view"
    leave = "leave"
    click = "click"
    rage_click = "rage_click"
    submit = "submit"
    change = "change"
    navigate = "navigate"
    unknown = "unknown"


class ParsedElements(BaseModel):
    element_type: str | None = None
    element_text: str | None = None
    attributes: dict[str, str] = {}
    hierarchy: list[str] = []


class EventClassification(BaseModel):
    event_type: EventType
    action_type: ActionType


class PageInfo(BaseModel):
    page_path: str
    page_title: str


class PostHogEvent(BaseModel):  # TODO consider renaming to "RawEventCreate"
    """Raw PostHog event schema for ingestion."""

    event: str
    distinct_id: str
    properties: PostHogProperties
    timestamp: datetime
    elements_chain: str | None

    model_config = {"from_attributes": True}


class RawEvent(BaseModel):
    """Internal, raw event version of posthog event, with better structure and job status tracking properties."""

    raw_event_id: UUID
    event_name: str
    user_id: str
    timestamp: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None
    properties: PostHogProperties
    processed_at: datetime | None = None
    status: RawEventStatus
    elements_chain: str | None = None

    model_config = {"from_attributes": True}

    @property
    def session_id(self) -> str:
        return self.properties.get("$session_id")

    @property
    def page_path(self) -> str:
        return self.properties.get("$pathname")


class RawEventUpdate(BaseModel):
    """Internal, raw event version of posthog event, with better structure and job status tracking properties."""

    event_name: str | None = None
    user_id: str | None = None
    timestamp: datetime = None
    properties: PostHogProperties | None = None
    processed_at: datetime | None = None
    status: RawEventStatus | None = None


class EnrichedEventCreate(BaseModel):
    raw_event_id: UUID
    user_id: str
    session_id: str
    timestamp: datetime
    event_name: str
    event_type: EventType
    semantic_label: str
    action_type: str | None = None
    page_path: str | None = None
    page_title: str | None = None
    element_type: str | None = None
    element_text: str | None = None
    context: EnrichedContext | None = None
    sequence_number: int | None = None


class EnrichedEvent(EnrichedEventCreate):
    enriched_event_id: UUID

    model_config = {"from_attributes": True}


class Session(BaseModel):
    """Common fields for all session variants"""

    session_id: str  # PostHog's $session_id
    created_at: datetime
    updated_at: datetime
    user_id: str
    started_at: datetime
    last_activity_at: datetime
    ended_at: datetime | None = None
    event_count: int = 0
    page_views_count: int = 0
    clicks_count: int = 0
    first_page: str | None = None
    last_page: str | None = None
    session_summary: str | None = None
    is_active: bool = True

    model_config = {"from_attributes": True}


class SessionCreate(BaseModel):
    """Model for creating a new session"""

    session_id: str  # PostHog's $session_id
    user_id: str
    started_at: datetime
    last_activity_at: datetime
    first_page: str | None = None
    is_active: bool = True


class SessionContext(BaseModel):
    """Session metadata for pattern detection"""

    session_id: str
    user_id: str
    started_at: datetime
    ended_at: datetime | None
    duration: timedelta | None  # None if session still active
    event_count: int
    page_views_count: int
    clicks_count: int
    first_page: str | None = None
    last_page: str | None = None
    is_active: bool

    @property
    def duration_seconds(self) -> float | None:
        """Session duration in seconds"""
        if self.duration:
            return self.duration.total_seconds()
        return None


class Pattern(BaseModel):
    code: str
    description: str
    severity: Severity


class UserContext(BaseModel):
    recent_events: list[EnrichedEvent]
    last_session_summary: str | None
    patterns: list[Pattern]
