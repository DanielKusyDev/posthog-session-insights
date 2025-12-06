from pytest import param, mark

from app.services.enrichment_services import parse_elements_chain, ParsedElements, classify_event, EventClassification, \
    EventType, ActionType, infer_action_from_custom_event


@mark.parametrize(
    "chain,expected",
    [
        param("", ParsedElements(), id="empty text"),
        param(
            'button.cursor-pointer:text="Shop"',
            ParsedElements(
                element_type="button",
                element_text="Shop",
                attributes={},
                hierarchy=["button"],
            ),
            id="simple_button_with_text",
        ),
        param(
            'img.w-full:attr__alt="foo"attr__src="https://example.com/image.jpg"',
            ParsedElements(
                element_type="img",
                element_text="foo",
                attributes={},
                hierarchy=["img"],
            ),
            id="image_with_text",
        ),
        param(
            'button.hover:attr__data-ph-capture-attribute-nav="home"text="Shop"',
            ParsedElements(
                element_type="button",
                element_text="Shop",
                attributes={"nav": "home"},
                hierarchy=["button"],
            ),
            id="single_custom_attribute",
        ),
        param(
            'button.cursor-pointer.hover:text-indigo-600:attr__class="cursor-pointer transition-colors text-gray-700 hover:text-indigo-600"attr__data-ph-capture-attribute-nav="home"text="Shop";nav.flex.gap-6;header.bg-white',
            ParsedElements(
                element_type="button",
                element_text="Shop",
                attributes={"nav": "home"},
                hierarchy=["button", "nav", "header"],
            ),
            id="multiple_custom_attributes",
        ),
        param(
            'button.btn:text="Click";div.container;section.main;main.app;body',
            ParsedElements(
                element_type="button",
                element_text="Click",
                attributes={},
                hierarchy=["button", "div", "section", "main", "body"],
            ),
            id="full_hierarchy_5_levels",
        ),
        param(
            "button;div;section;main;body;html;extra1;extra2",
            ParsedElements(
                element_type="button",
                element_text=None,
                attributes={},
                hierarchy=["button", "div", "section", "main", "body"],
            ),
            id="over_5_levels_hierarchy_truncate",
        ),
        param(
            (
                'img.duration-300:attr__alt="FPV Speedster"attr__class="w-full h-full '
                'object-cover"attr__data-ph-capture-attribute-product-id="3"'
                'attr__data-ph-capture-attribute-product-name="FPV Speedster";div.aspect-video;div.product-card'
            ),
            ParsedElements(
                element_type="img",
                element_text="FPV Speedster",
                attributes={"product-id": "3", "product-name": "FPV Speedster"},
                hierarchy=["img", "div", "div"],
            ),
            id="real_posthog_example",
        ),
        param(
            'input.border.rounded:attr__placeholder="Search products"',
            ParsedElements(
                element_type="input",
                element_text=None,
                attributes={},
                hierarchy=["input"],
            ),
            id="input_no_text_no_alt",
        ),
        param(
            'a.nav-link:attr__href="/about"text="About Us"',
            ParsedElements(
                element_type="a",
                element_text="About Us",
                attributes={},
                hierarchy=["a"],
            ),
            id="a_href",
        ),
        param(
            "button",
            ParsedElements(
                element_type="button",
                element_text=None,
                attributes={},
                hierarchy=["button"],
            ),
            id="element_type_only",
        ),
        param(
            'button:text="Add to Cart"',
            ParsedElements(
                element_type="button",
                element_text="Add to Cart",
                attributes={},
                hierarchy=["button"],
            ),
            id="text_with_spaces",
        ),
        param(
            'button:text="Price: $99.99"',
            ParsedElements(
                element_type="button",
                element_text="Price: $99.99",
                attributes={},
                hierarchy=["button"],
            ),
            id="text_with_special_characters",
        ),
        # Edge cases
        param(";;;", ParsedElements(), id="edge_semicolons_only"),
        param(
            "  button  ;  div  ",
            ParsedElements(element_type="button", hierarchy=["button", "div"]),
            id="chain_with_whitespace",
        ),
        param(
            "BUTTON",
            ParsedElements(element_type="button"),
            id="uppercase_element",
        ),
        # Text takes priority over alt
        param(
            'img:text="Logo"attr__alt="Company Logo"',
            ParsedElements(element_type="img", element_text="Logo", hierarchy=["img"]),
            id="text_over_alt",
        ),
        param(
            'img:text="Logo"',
            ParsedElements(element_type="img", element_text="Logo", hierarchy=["img"]),
            id="no_alt",
        ),
        param(
            'img:attr__alt="Company Logo"',
            ParsedElements(element_type="img", element_text="Company Logo", hierarchy=["img"]),
            id="no_text",
        ),
        param(
            (
                "button:"
                'attr__data-ph-capture-attribute-action="submit"'
                'attr__data-ph-capture-attribute-form-id="contact"'
                'attr__data-ph-capture-attribute-step="2"'
            ),
            ParsedElements(
                element_type="button",
                element_text=None,
                attributes={
                    "action": "submit",
                    "form-id": "contact",
                    "step": "2",
                },
                hierarchy=["button"],
            ),
            id="test_extraction_of_multiple_custom_attributes",
        ),
    ],
)
def test_parse_elements_chain(chain: str, expected: ParsedElements) -> None:
    assert parse_elements_chain(chain) == expected


def test_parse_elements_chain_hierarchy_limit() -> None:
    chain = "a;b;c;d;e;f;g;h;i;j"  # 10 levels
    result = parse_elements_chain(chain)

    assert len(result.hierarchy) == 5
    assert result.hierarchy == ["a", "b", "c", "d", "e"]


@mark.parametrize(
    "event_name,properties,expected",
    [
        # PostHog system events
        param(
            "$pageview",
            {},
            EventClassification(event_type=EventType.pageview, action_type=ActionType.view),
            id="pageview",
        ),
        param(
            "$pageleave",
            {},
            EventClassification(event_type=EventType.navigation, action_type=ActionType.leave),
            id="pageleave",
        ),
        param(
            "$rageclick",
            {},
            EventClassification(event_type=EventType.click, action_type=ActionType.rage_click),
            id="rageclick",
        ),
        # $autocapture with different event types
        param(
            "$autocapture",
            {"$event_type": "click"},
            EventClassification(event_type=EventType.click, action_type=ActionType.click),
            id="autocapture_click",
        ),
        param(
            "$autocapture",
            {"$event_type": "submit"},
            EventClassification(event_type=EventType.click, action_type=ActionType.submit),
            id="autocapture_submit",
        ),
        param(
            "$autocapture",
            {"$event_type": "change"},
            EventClassification(event_type=EventType.click, action_type=ActionType.change),
            id="autocapture_change",
        ),
        param(
            "$autocapture",
            {},  # No $event_type, should default to click
            EventClassification(event_type=EventType.click, action_type=ActionType.click),
            id="autocapture_no_event_type",
        ),
        param(
            "$autocapture",
            {"$event_type": "unknown_type"},  # Unknown type, should default to click
            EventClassification(event_type=EventType.click, action_type=ActionType.click),
            id="autocapture_unknown_type",
        ),
        # Custom events - click patterns
        param(
            "product_clicked",
            {},
            EventClassification(event_type=EventType.custom, action_type=ActionType.click),
            id="custom_clicked",
        ),
        param(
            "item_selected",
            {},
            EventClassification(event_type=EventType.custom, action_type=ActionType.click),
            id="custom_selected",
        ),
        param(
            "plan_chosen",
            {},
            EventClassification(event_type=EventType.custom, action_type=ActionType.click),
            id="custom_chosen",
        ),
        # Custom events - submit patterns
        param(
            "form_submitted",
            {},
            EventClassification(event_type=EventType.custom, action_type=ActionType.submit),
            id="custom_submitted",
        ),
        param(
            "payment_completed",
            {},
            EventClassification(event_type=EventType.custom, action_type=ActionType.submit),
            id="custom_completed",
        ),
        param(
            "checkout_finished",
            {},
            EventClassification(event_type=EventType.custom, action_type=ActionType.submit),
            id="custom_finished",
        ),
        # Custom events - navigate patterns
        param(
            "plan_upgrade_started",
            {},
            EventClassification(event_type=EventType.custom, action_type=ActionType.navigate),
            id="custom_started",
        ),
        param(
            "feature_opened",
            {},
            EventClassification(event_type=EventType.custom, action_type=ActionType.navigate),
            id="custom_opened",
        ),
        param(
            "page_viewed",
            {},
            EventClassification(event_type=EventType.custom, action_type=ActionType.navigate),
            id="custom_viewed",
        ),
        # Custom events - default fallback
        param(
            "random_custom_event",
            {},
            EventClassification(event_type=EventType.custom, action_type=ActionType.click),
            id="custom_default_fallback",
        ),
        # Unknown PostHog system events
        param(
            "$unknown_posthog_event",
            {},
            EventClassification(event_type=EventType.unknown, action_type=ActionType.unknown),
            id="unknown_system_event",
        ),
        param(
            "$some_new_event",
            {},
            EventClassification(event_type=EventType.unknown, action_type=ActionType.unknown),
            id="unknown_new_event",
        ),
    ],
)
def test_classify_event(event_name: str, properties: dict, expected: EventClassification) -> None:
    """Test classification of PostHog events into event_type and action_type"""
    assert classify_event(event_name, properties) == expected


@mark.parametrize(
    "event_name,expected",
    [
        # Click patterns
        param("product_clicked", ActionType.click, id="clicked"),
        param("item_selected", ActionType.click, id="selected"),
        param("option_chosen", ActionType.click, id="chosen"),
        param("PRODUCT_CLICKED", ActionType.click, id="uppercase_click"),
        param("Product_Selected", ActionType.click, id="mixedcase_click"),
        # Submit patterns
        param("form_submitted", ActionType.submit, id="submitted"),
        param("payment_completed", ActionType.submit, id="completed"),
        param("registration_finished", ActionType.submit, id="finished"),
        param("FORM_SUBMITTED", ActionType.submit, id="uppercase_submit"),
        # Navigate patterns
        param("feature_opened", ActionType.navigate, id="opened"),
        param("upgrade_started", ActionType.navigate, id="started"),
        param("dashboard_viewed", ActionType.navigate, id="viewed"),
        param("settings_navigated", ActionType.navigate, id="navigated"),
        # Default fallback
        param("random_event", ActionType.click, id="default"),
        param("some_action", ActionType.click, id="default_action"),
        param("", ActionType.click, id="empty_string"),
    ],
)
def test_infer_action_from_custom_event(event_name: str, expected: str) -> None:
    """Test inference of action_type from custom event names using heuristics"""
    assert infer_action_from_custom_event(event_name) == expected


def test_classify_event_case_insensitive_custom() -> None:
    """Test that custom event name matching is case-insensitive"""
    result_lower = classify_event("product_clicked", {})
    result_upper = classify_event("PRODUCT_CLICKED", {})
    result_mixed = classify_event("Product_Clicked", {})

    assert result_lower.action_type == ActionType.click
    assert result_upper.action_type == ActionType.click
    assert result_mixed.action_type == ActionType.click


def test_autocapture_with_extra_properties() -> None:
    """Test that $autocapture only looks at $event_type and ignores other properties"""
    result = classify_event(
        "$autocapture",
        {
            "$event_type": "submit",
            "product_id": "123",
            "user_action": "something_else",
        },
    )

    assert result.event_type == EventType.click
    assert result.action_type == ActionType.submit
