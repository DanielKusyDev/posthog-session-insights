from abc import ABC
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.db_models import RawEventStatus

PostHogProperties = dict[str, Any]
EnrichedContext = dict[str, Any]


class PostHogEvent(BaseModel):
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
    properties: PostHogProperties
    processed_at: datetime | None
    status: RawEventStatus


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
