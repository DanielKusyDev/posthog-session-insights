from datetime import datetime
from typing import Any

from pydantic import BaseModel

PostHogProperties = dict[str, Any]


class PostHogEvent(BaseModel):
    event: str
    distinct_id: str
    properties: PostHogProperties
    timestamp: datetime
