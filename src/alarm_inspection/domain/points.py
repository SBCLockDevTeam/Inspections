"""Deterministic point parsing and validation rules."""

from __future__ import annotations

import re
from numbers import Integral, Real
from dataclasses import dataclass
from typing import Iterable, Mapping

_POINT_RE = re.compile(r"^\s*(?:POINT|PT|P)\s*([0-9]+)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class PointDecision:
    address: int | None
    text: str
    accepted: bool
    reason: str


def normalize_point(value: object) -> int | None:
    """Return a point number for common source formats, otherwise None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real) and float(value).is_integer():
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    match = _POINT_RE.match(text)
    return int(match.group(1)) if match else None


def decide_point(row: Mapping[str, object]) -> PointDecision:
    raw_point = row.get("point")
    raw_text = "" if row.get("text") is None else str(row.get("text")).strip()
    combined = f"{raw_point or ''} {raw_text}".lower()
    if "unassigned" in combined:
        return PointDecision(None, raw_text, False, "contains unassigned")
    if raw_text.strip() in {"", "-"}:
        return PointDecision(None, raw_text, False, "missing or placeholder text")
    address = normalize_point(raw_point)
    if address is None:
        return PointDecision(None, raw_text, False, "point address not recognized")
    if not 1 <= address <= 255:
        return PointDecision(address, raw_text, False, "point address outside 1 through 255")
    if normalize_point(raw_text) is not None:
        return PointDecision(address, raw_text, False, "text is a placeholder point value")
    return PointDecision(address, raw_text, True, "accepted")


def first_event_by_point(events: Iterable[Mapping[str, object]]) -> dict[int, object]:
    """Return the earliest qualifying timestamp per normalized point."""
    selected: dict[int, object] = {}
    for event in events:
        event_type = str(event.get("event_type", "")).strip().upper()
        if event_type not in {"A", "T"}:
            continue
        point = normalize_point(event.get("point"))
        timestamp = event.get("timestamp")
        if point is None or timestamp is None:
            continue
        if point not in selected or timestamp < selected[point]:
            selected[point] = timestamp
    return selected

