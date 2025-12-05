from enum import Enum
from sqlalchemy import Table, Column, String, DateTime, JSON, Index, UUID, Enum as SAEnum
from sqlalchemy.sql import func

from app.db import metadata


class RawEventStatus(str, Enum):
    pending = "PENDING"
    processing = "PROCESSING"
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
    Column("properties", JSON),
    Column("processed_at", DateTime),
    Column(
        "status", SAEnum(*(s.value for s in RawEventStatus), create_type=False, name="event_status"), nullable=False
    ),
    Index("ix_raw_events_user_time", "user_id", "timestamp"),
)
