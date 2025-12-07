from enum import Enum
from sqlalchemy import (
    Table,
    Column,
    String,
    DateTime,
    JSON,
    Index,
    UUID,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Boolean,
    Text,
)
from sqlalchemy.sql import func

from app.db import metadata


class RawEventStatus(str, Enum):
    pending = "PENDING"
    done = "DONE"
    failed = "FAILED"


raw_event = Table(
    "raw_event",
    metadata,
    Column("raw_event_id", UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()),
    Column("event_name", String, nullable=False),
    Column("user_id", String, nullable=False),
    Column("timestamp", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.current_timestamp()),
    Column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    ),
    Column("properties", JSON),
    Column("elements_chain", String),
    Column("processed_at", DateTime),
    Column(
        "status", SAEnum(*(s.value for s in RawEventStatus), create_type=False, name="event_status"), nullable=False
    ),
    Index("ix_raw_events_user_time", "user_id", "timestamp"),
)

enriched_event = Table(
    "enriched_event",
    metadata,
    Column("enriched_event_id", UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()),
    Column("raw_event_id", UUID(as_uuid=True), ForeignKey("raw_event.raw_event_id"), nullable=False),
    Column("user_id", String, nullable=False),
    Column("session_id", String, nullable=False),
    Column("timestamp", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.current_timestamp()),
    Column("event_name", String, nullable=False),  # "$pageview", "product_clicked"
    Column("event_type", String, nullable=False),  # "pageview", "click", "custom"
    Column("semantic_label", String, nullable=False),  # "Clicked 'Shop' navigation button"
    Column("action_type", String),  # "view", "click", "navigate", "rage_click"
    Column("page_path", String),  # "/", "/about", "/billing"
    Column("page_title", String),  # "PostHog Demo Website"
    Column("element_type", String),  # "button", "img", "input"
    Column("element_text", String),  # "Shop", "FPV Speedster"
    Column("element_selector", String),  # "button[nav='home']" - uproszczona wersja
    Column("context", JSON),  # {product_id, product_name, nav_target, url, hierarchy}
    Column("sequence_number", Integer),
    Index("ix_enriched_user_timestamp", "user_id", "timestamp"),
    Index("ix_enriched_session_timestamp", "session_id", "timestamp"),
    Index("ix_enriched_timestamp", "timestamp"),
)

session = Table(
    "session",
    metadata,
    Column("session_id", String, primary_key=True),  # PostHog's $session_id
    Column("user_id", String, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("last_activity_at", DateTime(timezone=True), nullable=False),
    Column("ended_at", DateTime(timezone=True)),
    Column("event_count", Integer, default=0, nullable=False),
    Column("page_views_count", Integer, default=0, nullable=False),
    Column("clicks_count", Integer, default=0, nullable=False),
    Column("first_page", String),  # Metadata for LLM context
    Column("last_page", String),
    Column("session_summary", Text),  # ~500 chars generated summary
    Column("is_active", Boolean, default=True, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.current_timestamp()),
    Column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    ),
    Index("ix_session_user_started", "user_id", "started_at"),
    Index("ix_session_user_active", "user_id", "is_active"),
    Index("ix_session_active_activity", "is_active", "last_activity_at"),
)
