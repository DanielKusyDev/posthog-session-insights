from pytest import param, mark

from app.services.enrichment_services import parse_elements_chain, ParsedElements


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
