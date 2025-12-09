from typing import Any, Sequence

from app.config import SETTINGS
from app.models import ActionType, EnrichedEvent, EventType, PostHogProperties
from app.services.event_parsing import ParsedElements
from app.utils import hyphens_to_snake_case


async def build_context(
    event_name: str,
    properties: PostHogProperties,
    element_info: ParsedElements,
    excluded_keys: Sequence[str] = SETTINGS.context_exclude_keys,
) -> dict[str, Any]:
    """
    Build context dict with additional metadata for LLM.

    Extracts useful metadata from properties and element info while
    filtering out PostHog internal fields.
    """
    # Skip blacklisted PostHog properties
    context = {key: value for key, value in properties.items() if not key.startswith("$") and key not in excluded_keys}

    # Add custom attributes from elements_chain
    for attr_name, attr_value in element_info.attributes.items():
        context[hyphens_to_snake_case(attr_name)] = attr_value  # more python friendly

    # Add element hierarchy
    if element_info.hierarchy:
        context["hierarchy"] = element_info.hierarchy

    # 4. Add original event name (debugging)
    if event_name:
        context["posthog_event"] = event_name

    return context


async def generate_events_summary(events: list[EnrichedEvent]) -> str:
    """Generate human-readable session summary from session and events. Pure function, no DB queries."""
    if not events:
        return "No activity recorded"

    # Analyze events
    page_views = [e for e in events if e.event_type == EventType.pageview]
    clicks = [e for e in events if e.event_type == EventType.click]
    rage_clicks = [e for e in events if e.action_type == ActionType.rage_click]
    custom_events = [e for e in events if e.event_type == EventType.custom]

    # Extract unique pages (max settings.pages_in_summary_limit)
    unique_pages = []
    seen_pages = set()
    for e in page_views:
        if e.page_title and e.page_title not in seen_pages:
            unique_pages.append(e.page_title)
            seen_pages.add(e.page_title)
        if len(unique_pages) >= SETTINGS.pages_in_summary_limit:
            break

    # Build summary parts
    parts = []

    if unique_pages:
        pages_text = ", ".join(unique_pages)
        parts.append(f"Viewed {len(page_views)} pages including {pages_text}")

    if clicks:
        parts.append(f"Clicked {len(clicks)} times")

    if rage_clicks:
        parts.append(f"Rage-clicked {len(rage_clicks)} times (frustration detected)")

    if custom_events:
        parts.append(f"Triggered {len(custom_events)} custom events")

    if not parts:
        parts = ["No significant activity"]

    summary = ". ".join(parts)
    if not summary.endswith("."):
        summary += "."

    return summary
