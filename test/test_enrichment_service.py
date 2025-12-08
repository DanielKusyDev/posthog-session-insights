from uuid import UUID

from pytest import mark, param

from app.models import RawEvent
from app.services.event_parsing import ParsedElements
from app.services.event_services import build_context


@mark.parametrize(
    "event_properties,element_info,event_name,expected",
    [
        # Basic case - catch-all non-$ properties
        param(
            {"product_id": "3", "product_name": "FPV Speedster"},
            ParsedElements(),
            "product_clicked",
            {
                "product_id": "3",
                "product_name": "FPV Speedster",
                "posthog_event": "product_clicked",
            },
            id="basic_custom_properties",
        ),
        # Filter out $ properties
        param(
            {"$pathname": "/about", "title": "About Us"},
            ParsedElements(),
            "$pageview",
            {"title": "About Us", "posthog_event": "$pageview"},
            id="filter_dollar_properties",
        ),
        # Filter out excluded keys
        param(
            {"token": "secret", "distinct_id": "123", "user_role": "admin"},
            ParsedElements(),
            "custom_event",
            {"user_role": "admin", "posthog_event": "custom_event"},
            id="filter_excluded_keys",
        ),
        # Element attributes with hyphen conversion
        param(
            {},
            ParsedElements(attributes={"product-id": "3", "product-name": "Drone"}),
            "click",
            {
                "product_id": "3",
                "product_name": "Drone",
                "posthog_event": "click",
            },
            id="element_attributes_hyphen_conversion",
        ),
        # Hierarchy included
        param(
            {},
            ParsedElements(hierarchy=["button", "nav", "header", "body", "html"]),
            "click",
            {
                "hierarchy": ["button", "nav", "header", "body", "html"],
                "posthog_event": "click",
            },
            id="hierarchy_all_levels",
        ),
        # Combined - properties + attributes + hierarchy
        param(
            {"user_role": "admin", "$time": 123456},
            ParsedElements(
                attributes={"nav": "home", "form-id": "contact"},
                hierarchy=["button", "form"],
            ),
            "$autocapture",
            {
                "user_role": "admin",
                "nav": "home",
                "form_id": "contact",
                "hierarchy": ["button", "form"],
                "posthog_event": "$autocapture",
            },
            id="combined_all",
        ),
        # Empty case
        param(
            {},
            ParsedElements(),
            None,
            {"posthog_event": "test"},
            id="empty_everything",
        ),
        # All excluded
        param(
            {"$lib": "web", "$session_id": "123", "token": "abc"},
            ParsedElements(),
            "test",
            {"posthog_event": "test"},
            id="all_properties_excluded",
        ),
    ],
)
@mark.asyncio
async def test_build_context(
    event_properties: dict,
    element_info: ParsedElements,
    event_name: str | None,
    expected: dict,
) -> None:
    """Test context building from event properties and element info"""
    # Create mock RawEvent
    raw_event = RawEvent(
        raw_event_id=UUID("12345678123456781234567812345678"),
        event_name=event_name or "test",
        user_id="user-123",
        timestamp="2025-01-01T00:00:00Z",
        properties=event_properties,
        status="PENDING",
    )

    result = await build_context(raw_event.event_name, raw_event.properties, element_info)
    assert result == expected


@mark.asyncio
async def test_build_context_attribute_override() -> None:
    """Test that element attributes override properties with same key"""
    raw_event = RawEvent(
        raw_event_id=UUID("12345678123456781234567812345678"),
        event_name="click",
        user_id="user-123",
        timestamp="2025-01-01T00:00:00Z",
        properties={"product_id": "old"},
        status="PENDING",
    )

    element_info = ParsedElements(attributes={"product-id": "new"})
    result = await build_context(raw_event.event_name, raw_event.properties, element_info)

    # Element attribute should override property
    assert result["product_id"] == "new"
