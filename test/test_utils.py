from pytest import param, mark
from app.utils import truncate_text, capitalize_first_letter, humanize_snake_case_string


@mark.parametrize(
    "text,max_length,expected",
    [
        param("short text", 20, "short text", id="no_truncation"),
        param("exact length", 12, "exact length", id="exact_length"),
        param("", 10, "", id="empty_string"),
        param("this is a very long text", 10, "this is...", id="truncate_simple"),
        param("abcdefghijklmnop", 10, "abcdefg...", id="truncate_exact"),
        param("a" * 100, 20, "a" * 17 + "...", id="truncate_long"),
        param("abc", 3, "abc", id="exact_max_length"),
        param("abcd", 3, "...", id="shorter_than_ellipsis"),
        param("text", 4, "t...", id="min_truncation"),
        param("text", 0, "...", id="max_length_zero"),
    ],
)
def test_truncate_text(text: str, max_length: int, expected: str) -> None:
    """Test text truncation with ellipsis"""
    assert truncate_text(text, max_length) == expected


@mark.parametrize(
    "text,expected",
    [
        param("hello world", "Hello world", id="lowercase"),
        param("HELLO WORLD", "HELLO WORLD", id="uppercase"),
        param("hello", "Hello", id="single_word"),
        param("", "", id="empty_string"),
        param("a", "A", id="single_char"),
        param("1234", "1234", id="starts_with_number"),
        param(" leading space", " leading space", id="leading_space"),
        param("Already capitalized", "Already capitalized", id="already_capitalized"),
        param("!hello", "!hello", id="starts_with_special_char"),
        param("über", "Über", id="unicode"),
    ],
)
def test_capitalize_first_letter(text: str, expected: str) -> None:
    assert capitalize_first_letter(text) == expected


@mark.parametrize(
    "text,expected",
    [
        param("product_clicked", "product clicked", id="simple_snake_case"),
        param("plan_upgrade_started", "plan upgrade started", id="multiple_underscores"),
        param("user_profile_settings", "user profile settings", id="three_words"),
        param("no_underscores", "no underscores", id="single_underscore"),
        param("single", "single", id="no_underscores"),
        param("", "", id="empty_string"),
        param("_leading_underscore", " leading underscore", id="leading_underscore"),
        param("trailing_underscore_", "trailing underscore ", id="trailing_underscore"),
        param("multiple___underscores", "multiple   underscores", id="multiple_consecutive"),
        param("Product_Clicked", "product clicked", id="mixed_case"),
        param("PRODUCT_CLICKED", "product clicked", id="all_caps"),
        param("event_123_triggered", "event 123 triggered", id="with_numbers"),
    ],
)
def test_humanize_snake_case_string(text: str, expected: str) -> None:
    """Test conversion of snake_case to human-readable format"""
    assert humanize_snake_case_string(text) == expected
