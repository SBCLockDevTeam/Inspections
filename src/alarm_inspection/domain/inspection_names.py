"""Deterministic inspection names and conservative legacy location extraction."""
from __future__ import annotations

from datetime import date
import re

STATE_CODES = frozenset("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY AS GU MP PR VI".split())
_STREET_SUFFIX = re.compile(r"\b(?:STREET|ST|ROAD|RD|AVENUE|AVE|BOULEVARD|BLVD|DRIVE|DR|HIGHWAY|HWY|PARKWAY|PKWY|LANE|LN|COURT|CT|CIRCLE|CIR|TRAIL|TRL|WAY|PLACE|PL|TERRACE|TER)\b\.?", re.I)
_STATE_ZIP = re.compile(r"(?:^|[\s,])([A-Za-z]{2})(?:\s+\d{5}(?:-\d{4})?)?\s*$")


def normalize_city(value: str) -> str:
    value = " ".join(value.split()).strip(" ,")
    return value.title() if value.isupper() or value.islower() else value


def normalize_state(value: str) -> str:
    value = value.strip().upper()
    return value if value in STATE_CODES else ""


def location_from_address(address: str) -> tuple[str, str]:
    """Extract explicit city/state text; never infer a state from a city name."""
    value = re.sub(r",?\s+(?:US|USA|United States)\s*$", "", address.strip(), flags=re.I)
    match = _STATE_ZIP.search(value)
    state = normalize_state(match.group(1)) if match else ""
    if state:
        value = value[:match.start()].strip(" ,")
    # A comma-delimited city takes precedence. Otherwise strip the street and unit.
    if "," in value:
        city = value.rsplit(",", 1)[-1].strip()
    elif re.search(r"\d", value):
        suffixes = list(_STREET_SUFFIX.finditer(value))
        if not suffixes:
            return "", state
        city = value[suffixes[-1].end():].strip()
        city = re.sub(r"^(?:#\s*\S+|(?:SUITE|STE|UNIT|APT)\s+\S+)\s*", "", city, flags=re.I)
    else:
        city = value
    if re.search(r"\d", city):
        city = ""
    return normalize_city(city), state


def build_inspection_name(store_number: str, city: str, state: str, start_date: date) -> str:
    return f"{store_number.strip() or 'Store Required'}-{normalize_city(city) or 'City Required'}-{normalize_state(state) or 'ST'}-{start_date:%m-%Y}"
