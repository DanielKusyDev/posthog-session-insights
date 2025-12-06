def truncate_text(text: str, max_length: int) -> str:
    """
    Truncate text to max_length if necessary.

    Adds ellipsis (...) if truncated.
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - 3] + "..."


def capitalize_first_letter(text: str) -> str:
    """Capitalize first letter of text."""
    if not text:
        return text

    return text[0].upper() + text[1:]


def humanize_snake_case_string(text: str) -> str:
    """
    Convert snake_case string to human-readable format.

    Examples:
        "product_clicked" → "product clicked"
        "plan_upgrade_started" → "plan upgrade started"
    """
    return text.replace("_", " ").lower()
