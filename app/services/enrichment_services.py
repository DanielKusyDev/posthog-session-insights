import re

from pydantic import BaseModel


class ParsedElements(BaseModel):
    element_type: str | None = None
    element_text: str | None = None
    attributes: dict[str, str] = {}
    hierarchy: list[str] = []


def parse_elements_chain(chain: str) -> ParsedElements:
    """
    Parse PostHog elements_chain string into structured element information.

    Extraction order:
    1. Element type - HTML Tag name before '.' or ':' (normalized to lowercase)
    2. Element text - from `text="..."` attribute or `attr__alt="..."` in case of images
    3. Custom attributes - all `attr__data-ph-capture-attribute-*` attributes
    4. Hierarchy - first 5 DOM levels from chain segments

    Examples:
        >>> parse_elements_chain('button:text="Shop"')
        ParsedElements(element_type='button', element_text='Shop', ...)

        >>> parse_elements_chain('img:attr__alt="Logo"attr__data-ph-capture-attribute-nav="home";div;header')
        ParsedElements(element_type='img', element_text='Logo', attributes={'nav': 'home'},
                       hierarchy=['img', 'div', 'header'])
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
