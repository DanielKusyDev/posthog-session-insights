import re

from app.models import ActionType, EventClassification, EventType, PageInfo, ParsedElements, PostHogProperties


def parse_elements_chain(chain: str) -> ParsedElements:
    """
    Parse PostHog elements_chain string into structured element information.

    Extraction order:
    1. Element type - HTML Tag name before '.' or ':' (normalized to lowercase)
    2. Element text - from `text="..."` attribute or `attr__alt="..."` in case of images
    3. Custom attributes - all `attr__data-ph-capture-attribute-*` attributes
    4. Hierarchy - first 5 DOM levels from chain segments
    """
    if not chain:
        return ParsedElements()

    # Split into segments (button;nav;header)
    segments = chain.split(";")
    first_segment = segments[0].strip()

    # Extract element type (part before '.' or ':')
    element_type_match = re.match(r"^([a-z0-9]+)", first_segment, re.IGNORECASE)
    element_type = element_type_match.group(1).lower() if element_type_match else None

    # Extract text with regex (handles escaped quotes)
    text_match = re.search(r'text="([^"]*)"', first_segment)
    element_text = text_match.group(1) if text_match else None

    # Extract alt (for images)
    if not element_text:
        alt_match = re.search(r'attr__alt="([^"]*)"', first_segment)
        element_text = alt_match.group(1) if alt_match else None

    # Extract custom attributes (data-ph-capture-attribute-*)
    attributes = {}
    attr_matches = re.finditer(r'attr__data-ph-capture-attribute-([^=]+)="([^"]*)"', first_segment)
    for match in attr_matches:
        attr_name = match.group(1)
        attr_value = match.group(2)
        attributes[attr_name] = attr_value

    # Build hierarchy (just element types)
    hierarchy = []
    for segment in segments[:5]:  # Limit to 5 levels
        elem_match = re.match(r"^([a-z0-9]+)", segment.strip())
        if elem_match:
            hierarchy.append(elem_match.group(1))

    return ParsedElements(
        element_type=element_type,
        element_text=element_text,
        attributes=attributes,
        hierarchy=hierarchy,
    )


def _classify_autocapture(properties: PostHogProperties) -> EventClassification:
    # Check properties.$event_type to determine specific action
    autocapture_type = properties.get("$event_type", "click")  # click as default
    match autocapture_type:
        case "click":
            return EventClassification(event_type=EventType.click, action_type=ActionType.click)
        case "submit":
            return EventClassification(event_type=EventType.click, action_type=ActionType.submit)
        case "change":
            return EventClassification(event_type=EventType.click, action_type=ActionType.change)
    return EventClassification(event_type=EventType.click, action_type=ActionType.click)


def infer_action_from_custom_event(event_name: str) -> str:
    """
    Infer action_type from custom event name.

    We assume that names of the events were chosen with attention to the actual action it represents thus this is not
    an algorithm but rather a heuristic.
    """
    event_lower = event_name.lower()

    # Click patterns
    if any(keyword in event_lower for keyword in ["click", "select", "choose"]):
        return ActionType.click

    # Submit patterns
    if any(keyword in event_lower for keyword in ["submit", "complete", "finish"]):
        return ActionType.submit

    # Navigate patterns
    if any(keyword in event_lower for keyword in ["start", "open", "view", "navigate"]):
        return ActionType.navigate

    # Default for custom events
    return ActionType.click


def classify_event(event_name: str, properties: PostHogProperties) -> EventClassification:
    """
    Classify PostHog event into event_type and action_type.

    Classification logic:
    1. PostHog system events ($pageview, $autocapture, etc.) - use mapping
    2. $autocapture - check properties.$event_type for specific action
    3. Custom events (no $ prefix) - classify as "custom"
    4. Unknown - fallback to "unknown"
    """
    # PostHog system events
    match event_name:
        case "$pageview":
            return EventClassification(event_type=EventType.pageview, action_type=ActionType.view)
        case "$pageleave":
            return EventClassification(event_type=EventType.navigation, action_type=ActionType.leave)
        case "$rageclick":
            return EventClassification(event_type=EventType.click, action_type=ActionType.rage_click)
        case "$autocapture":
            return _classify_autocapture(properties)

    if not event_name.startswith("$"):  # Custom events (no $ prefix), try to infer action from event name
        action_type = infer_action_from_custom_event(event_name)
        return EventClassification(event_type=EventType.custom, action_type=action_type)

    return EventClassification(event_type=EventType.unknown, action_type=ActionType.unknown)


def normalize_page_path(page_path: str) -> str:
    return "/" if page_path == "/" else page_path.rstrip("/")


def humanize_page_path(page_path: str) -> str:
    """
    Convert page path to human-readable page name.
    Example:
        >>> humanize_page_path("/about")
        "about page"
    """
    path = page_path.strip("/")

    if not path:
        return "home page"

    first_segment = path.split("/")[0]  # Take first segment (e.g., "billing/settings" → "billing")
    humanized = first_segment.replace("_", " ").replace("-", " ")  # Replace underscores/hyphens with spaces
    return f"{humanized} page"


def extract_page_info(properties: PostHogProperties) -> PageInfo:
    """Extract page path and title from PostHog event properties."""

    page_path = properties.get("$pathname", "/")
    page_path = normalize_page_path(page_path)  # remove trailing slashes
    page_title = properties.get("title", humanize_page_path(page_path))

    return PageInfo(page_path=page_path, page_title=page_title)
