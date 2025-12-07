from app.services.event_parsing import ActionType, EventType, PageInfo, ParsedElements
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
        label = truncate_text(label, self.max_length)
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

        return humanize_snake_case_string(event_name).lower()

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
