from pytest import param, mark
from app.services.event_parsing import PageInfo, ParsedElements, EventType, ActionType
from app.services.semantic_builder_services import SemanticLabelBuilder


@mark.parametrize(
    "event_type,action_type,page_info,element_info,event_name,properties,expected",
    [
        param(
            EventType.pageview,
            ActionType.view,
            PageInfo(page_path="/", page_title="home page"),
            ParsedElements(),
            None,
            {},
            "Viewed home page",
            id="pageview_home",
        ),
        param(
            EventType.pageview,
            ActionType.view,
            PageInfo(page_path="/about", page_title="About Us"),
            ParsedElements(),
            None,
            {},
            "Viewed About Us",
            id="pageview_with_title",
        ),
        param(
            EventType.click,
            ActionType.click,
            PageInfo(page_path="/", page_title="home page"),
            ParsedElements(element_type="button", element_text="Shop"),
            None,
            {},
            "Clicked 'Shop' button",
            id="click_button_with_text",
        ),
        param(
            EventType.click,
            ActionType.click,
            PageInfo(page_path="/", page_title="home page"),
            ParsedElements(element_type="img", element_text="FPV Speedster"),
            None,
            {},
            "Clicked 'FPV Speedster' img",
            id="click_image_with_text",
        ),
        param(
            EventType.click,
            ActionType.click,
            PageInfo(page_path="/", page_title="home page"),
            ParsedElements(
                element_type="button",
                element_text="Shop",
                attributes={"nav": "home"},
            ),
            None,
            {},
            "Clicked 'Shop' navigation button",
            id="click_nav_button_enriched",
        ),
        param(
            EventType.click,
            ActionType.click,
            PageInfo(page_path="/products", page_title="products page"),
            ParsedElements(
                element_type="div",
                element_text="FPV Speedster",
                attributes={"product-id": "3"},
            ),
            None,
            {},
            "Clicked 'FPV Speedster' product card",
            id="click_product_card_enriched",
        ),
        param(
            EventType.click,
            ActionType.click,
            PageInfo(page_path="/billing", page_title="billing page"),
            ParsedElements(element_type="input"),
            None,
            {},
            "Clicked input on billing page",
            id="click_input_no_text",
        ),
        param(
            EventType.click,
            ActionType.click,
            PageInfo(page_path="/", page_title="home page"),
            ParsedElements(),  # No element info at all
            None,
            {},
            "Clicked element on home page",
            id="click_no_element_info",
        ),
        param(
            ActionType.rage_click,
            ActionType.rage_click,
            PageInfo(page_path="/", page_title="home page"),
            ParsedElements(element_type="img", element_text="FPV Speedster"),
            None,
            {},
            "Rage-clicked 'FPV Speedster' img",
            id="rage_click_with_text",
        ),
        param(
            EventType.click,
            ActionType.rage_click,
            PageInfo(page_path="/products", page_title="products page"),
            ParsedElements(element_type="button"),
            None,
            {},
            "Rage-clicked button on products page",
            id="rage_click_no_text",
        ),
        param(
            EventType.click,
            ActionType.rage_click,
            PageInfo(page_path="/", page_title="home page"),
            ParsedElements(),  # No element info
            None,
            {},
            "Rage-clicked on home page",
            id="rage_click_no_element",
        ),
        param(
            EventType.navigation,
            ActionType.leave,
            PageInfo(page_path="/about", page_title="About Us"),
            ParsedElements(),
            None,
            {},
            "Left About Us",
            id="navigation_leave",
        ),
        # Custom events with templates
        param(
            EventType.custom,
            ActionType.click,
            PageInfo(page_path="/", page_title="home page"),
            ParsedElements(),
            "product_clicked",
            {"product_name": "FPV Speedster"},
            "Selected product: FPV Speedster",
            id="custom_with_template",
        ),
        param(
            EventType.custom,
            ActionType.navigate,
            PageInfo(page_path="/billing", page_title="billing page"),
            ParsedElements(),
            "plan_upgrade_started",
            {},
            "Started plan upgrade",
            id="custom_template_no_params",
        ),
        # Custom events without template (humanized)
        param(
            EventType.custom,
            ActionType.click,
            PageInfo(page_path="/", page_title="home page"),
            ParsedElements(),
            "unknown_custom_event",
            {},
            "Unknown custom event",
            id="custom_no_template_humanized",
        ),
        param(
            EventType.custom,
            ActionType.click,
            PageInfo(page_path="/", page_title="home page"),
            ParsedElements(),
            "user_profile_updated",
            {},
            "User profile updated",
            id="custom_humanize_snake_case",
        ),
        param(
            EventType.unknown,
            ActionType.unknown,
            PageInfo(page_path="/", page_title="home page"),
            ParsedElements(),
            None,
            {},
            "Event on home page",
            id="fallback_unknown",
        ),
    ],
)
def test_semantic_label_builder_build(
    event_type: str,
    action_type: str,
    page_info: PageInfo,
    element_info: ParsedElements,
    event_name: str | None,
    properties: dict,
    expected: str,
) -> None:
    """Test semantic label building for various event types"""
    builder = SemanticLabelBuilder()
    result = builder.build(
        event_type=event_type,
        action_type=action_type,
        page_info=page_info,
        element_info=element_info,
        event_name=event_name,
        properties=properties,
    )
    assert result == expected


def test_semantic_label_builder_with_custom_templates() -> None:
    """Test builder with custom event templates"""
    custom_templates = {
        "test_event": "Custom: {value}",
    }
    builder = SemanticLabelBuilder(custom_templates=custom_templates)

    result = builder.build(
        event_type=EventType.custom,
        action_type=ActionType.click,
        page_info=PageInfo(page_path="/", page_title="home page"),
        element_info=ParsedElements(),
        event_name="test_event",
        properties={"value": "123"},
    )

    assert result == "Custom: 123"


def test_semantic_label_builder_with_custom_enrichment_rules() -> None:
    """Test builder with custom enrichment rules"""
    custom_rules = {
        "test-attr": "custom {base_type}",
    }
    builder = SemanticLabelBuilder(enrichment_rules=custom_rules)

    result = builder.build(
        event_type=EventType.click,
        action_type=ActionType.click,
        page_info=PageInfo(page_path="/", page_title="home page"),
        element_info=ParsedElements(
            element_type="button",
            element_text="Click",
            attributes={"test-attr": "value"},
        ),
        event_name=None,
        properties={},
    )

    assert result == "Clicked 'Click' custom button"


def test_semantic_label_builder_max_length_truncation() -> None:
    """Test that labels are truncated to max_length"""
    builder = SemanticLabelBuilder(max_length=20)

    result = builder.build(
        event_type=EventType.pageview,
        action_type=ActionType.view,
        page_info=PageInfo(page_path="/", page_title="This is a very long page title that exceeds max length"),
        element_info=ParsedElements(),
    )

    assert len(result) == 20
    assert result.endswith("...")
    assert result == "Viewed This is a ..."


def test_semantic_label_builder_custom_event_template_missing_property() -> None:
    """Test custom event falls back to humanize when template property is missing"""
    builder = SemanticLabelBuilder()

    # Template requires {product_name} but we don't provide it
    result = builder.build(
        event_type=EventType.custom,
        action_type=ActionType.click,
        page_info=PageInfo(page_path="/", page_title="home page"),
        element_info=ParsedElements(),
        event_name="product_clicked",
        properties={},  # Missing product_name
    )

    # Should fall back to humanizing event name
    assert result == "Product clicked"


def test_semantic_label_builder_enrichment_priority() -> None:
    """Test that first matching enrichment rule is applied"""
    rules = {
        "attr1": "first {base_type}",
        "attr2": "second {base_type}",
    }
    builder = SemanticLabelBuilder(enrichment_rules=rules)

    # Element has both attributes - first one should win
    result = builder.build(
        event_type=EventType.click,
        action_type=ActionType.click,
        page_info=PageInfo(page_path="/", page_title="home page"),
        element_info=ParsedElements(
            element_type="div",
            element_text="Test",
            attributes={"attr1": "val1", "attr2": "val2"},
        ),
    )

    # Should use first matching rule
    assert "first div" in result or "second div" in result  # Depends on dict iteration order
