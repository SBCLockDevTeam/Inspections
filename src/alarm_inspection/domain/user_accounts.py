"""Validation for administrator-assigned login IDs and contact emails."""
import re
import unicodedata


def clean_user_id(value: object) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ValueError('User ID is required.')
    value = value.strip()
    if not value or len(value) > 255 or any(unicodedata.category(c).startswith('C') for c in value):
        raise ValueError('User ID must contain 1–255 visible characters.')
    return value, value.casefold()


def clean_email(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError('A valid email address is required.')
    value = value.strip().lower()
    if len(value) > 255 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise ValueError('A valid email address is required.')
    return value
