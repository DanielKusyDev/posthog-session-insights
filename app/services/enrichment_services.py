import re
from enum import Enum

from pydantic import BaseModel

from app.models import PostHogProperties
from app.utils import truncate_text, capitalize_first_letter, humanize_snake_case_string

DEFAULT_CUSTOM_EVENT_TEMPLATES: dict[str, str] = {  # TODO move to the database
    "product_clicked": "Selected product: {product_name}",
    "plan_upgrade_started": "Started plan upgrade",
    "plan_upgrade_completed": "Completed plan upgrade to {plan_name}",
    "form_submitted": "Submitted {form_name} form",
}
DEFAULT_ELEMENT_ENRICHMENT_RULES: dict[str, str] = {  # TODO move to the database
    "nav": "navigation {base_type}",
    "product-id": "product card",
    "product-name": "product card",
    "form-id": "{base_type} in form",
}
SEMANTIC_LABEL_MAX_LENGTH = 150


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
        case "$pageview":
            return EventClassification(event_type=EventType.pageview, action_type=ActionType.view)
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


class SemanticLabelBuilder:
    """
    Builder for creating LLM-friendly semantic labels from event data.

    Configurable with custom templates and constraints.
    """

    def __init__(
        self,
        custom_templates: dict[str, str] | None = None,
        enrichment_rules: dict[str, str] | None = None,
        max_length: int = SEMANTIC_LABEL_MAX_LENGTH,
    ):
        self.enrichment_rules = enrichment_rules or DEFAULT_ELEMENT_ENRICHMENT_RULES
        self.custom_templates = custom_templates or DEFAULT_CUSTOM_EVENT_TEMPLATES
        self.max_length = max_length

    def build(
        self,
        event_type: str,
        action_type: str,
        page_info: PageInfo,
        element_info: ParsedElements,
        event_name: str | None = None,
        properties: dict[str, any] | None = None,
    ) -> str:
        """
        Build human-readable semantic label for LLM consumption.

        Routes to appropriate builder based on event_type and action_type.
        """
        properties = properties or {}

        # Dispatch to appropriate builder
        match (event_type, action_type):
            case (EventType.pageview, _):
                label = self._build_pageview_label(page_info)

            case (_, ActionType.rage_click):
                label = self._build_rage_click_label(element_info, page_info)

            case (EventType.click, _):
                label = self._build_click_label(element_info, page_info)

            case (EventType.navigation, ActionType.leave):
                label = self._build_navigation_label(page_info)

            case (EventType.custom, _):
                label = self._build_custom_label(event_name, properties)

            case _:
                label = self._build_fallback_label(page_info)

        # Post-processing
        label = truncate_text(label, SEMANTIC_LABEL_MAX_LENGTH)
        label = capitalize_first_letter(label)

        return label

    def _build_pageview_label(self, page_info: PageInfo) -> str:
        return f"viewed {page_info.page_title}"

    def _build_click_label(self, element_info: ParsedElements, page_info: PageInfo) -> str:
        """Build label for click events."""
        if element_info.element_text:
            element_type = self._enrich_element_type(element_info)
            return f"clicked '{element_info.element_text}' {element_type}"

        # Fallback without element text
        element_type = element_info.element_type or "element"
        return f"clicked {element_type} on {page_info.page_title}"

    def _build_rage_click_label(self, element_info: ParsedElements, page_info: PageInfo) -> str:
        """Build label for rage click events (user frustration signal)."""
        if element_info.element_text:
            element_type = element_info.element_type or "element"
            return f"rage-clicked '{element_info.element_text}' {element_type}"

        if element_info.element_type:
            return f"rage-clicked {element_info.element_type} on {page_info.page_title}"

        return f"rage-clicked on {page_info.page_title}"

    def _build_navigation_label(self, page_info: PageInfo) -> str:
        """Build label for navigation events (page leave)."""
        return f"left {page_info.page_title}"

    def _build_custom_label(self, event_name: str | None, properties: dict[str, any]) -> str:
        """
        Build label for custom events.

        Tries to use configured template, falls back to humanizing event name.
        """
        if not event_name:
            return "custom event"

        # Try configured template
        if event_name in self.custom_templates:
            template = self.custom_templates[event_name]
            try:
                return template.format(**properties)
            except KeyError:
                pass  # Missing property, fall through to humanize

        # Fallback: humanize event name
        return humanize_snake_case_string(event_name)

    def _build_fallback_label(self, page_info: PageInfo) -> str:
        """Ultimate fallback for unknown event types."""
        return f"event on {page_info.page_title}"

    def _enrich_element_type(self, element_info: ParsedElements) -> str:
        """
        Enrich element type with context from custom attributes.

        Uses configurable enrichment rules.

        Examples:
            type='button', attributes={'nav': 'home'} → "navigation button"
            type='card', attributes={'product-id': '3'} → "product card"
        """
        base_type = element_info.element_type or "element"

        # Apply enrichment rules in priority order
        for attr_name in element_info.attributes:
            if attr_name in self.enrichment_rules:
                template = self.enrichment_rules[attr_name]
                return template.format(base_type=base_type)

        # No enrichment matched
        return base_type

