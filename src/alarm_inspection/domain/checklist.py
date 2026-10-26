"""Deterministic validation of checklist definitions and captured values."""


def validate_options(input_type: str, options: list[str]) -> list[str]:
    if input_type not in {"checkbox", "textbox", "dropdown"}:
        raise ValueError("Choose checkbox, textbox, or dropdown.")
    cleaned = [" ".join(option.split()) for option in options]
    if len(cleaned) > 50 or any(not option or len(option) > 120 for option in cleaned):
        raise ValueError("Provide up to 50 nonempty dropdown choices, each at most 120 characters.")
    if len({option.casefold() for option in cleaned}) != len(cleaned):
        raise ValueError("Dropdown choices must be unique.")
    if input_type == "dropdown" and not cleaned:
        raise ValueError("Add at least one dropdown choice.")
    if input_type != "dropdown" and cleaned:
        raise ValueError("Only dropdown items can have choices.")
    return cleaned


def validate_answer(input_type: str, completed: bool | None, value: str | None, options: list[str]):
    if input_type == "checkbox":
        if completed is None or value is not None:
            raise ValueError("A checkbox requires a true or false completion value.")
        return completed, ""
    if value is None or completed is not None:
        raise ValueError("Provide a text value for this checklist item.")
    if len(value) > 2000:
        raise ValueError("Values must be at most 2000 characters.")
    if input_type == "dropdown" and value and value not in options:
        raise ValueError("Select a current dropdown choice or clear the value.")
    return bool(value.strip()), value
