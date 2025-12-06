from abc import ABC
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.db_models import RawEventStatus

PostHogProperties = dict[str, Any]
EnrichedContext = dict[str, Any]


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

    raw_event_id: str
    event_name: str
    user_id: str
    timestamp: datetime
    created_at: datetime | None
    updated_at: datetime | None
    properties: PostHogProperties
    processed_at: datetime | None
    status: RawEventStatus

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


class EnrichedEventBase(BaseModel, ABC):
    """Common fields for all enriched event variants"""

    user_id: str
    session_id: str
    timestamp: datetime
    event_name: str
    event_type: str
    semantic_label: str
    action_type: str | None = None
    page_path: str | None = None
    page_title: str | None = None
    element_type: str | None = None
    element_text: str | None = None
    context: EnrichedContext | None = None
    sequence_number: int | None = None


class EnrichedEventCreate(EnrichedEventBase):
    """Model for creating enriched event (without auto-generated fields)"""

    raw_event_id: UUID


class EnrichedEvent(EnrichedEventBase):
    """Full enriched event model (with auto-generated fields)"""

    enriched_event_id: UUID
    raw_event_id: UUID
    created_at: datetime

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


class SessionUpdate(BaseModel):
    """Model for updating session (all fields optional)"""

    last_activity_at: datetime | None = None
    ended_at: datetime | None = None
    event_count: int | None = None
    page_views_count: int | None = None
    clicks_count: int | None = None
    last_page: str | None = None
    session_summary: str | None = None
    is_active: bool | None = None
