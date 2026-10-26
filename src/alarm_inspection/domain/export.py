"""Deterministic completion checks for final initiating device reports."""
from datetime import datetime

from alarm_inspection.domain.points import normalize_point


def validate_export_rows(rows: list[dict[str, str]]) -> str | None:
    if not isinstance(rows, list) or not rows:
        return "At least one accepted point is required before export."
    problems = []
    seen = set()
    for index, row in enumerate(rows, 1):
        point = normalize_point(row.get("address"))
        label = f"Point {point}" if point is not None else f"Row {index}"
        if point is None or not 1 <= point <= 255:
            problems.append(f"{label}: valid address (1–255) required")
        elif point in seen:
            problems.append(f"{label}: duplicate address requires review")
        seen.add(point)
        for field, name in (("text", "description"), ("location", "location")):
            if not str(row.get(field) or "").strip():
                problems.append(f"{label}: {name} required")
        try:
            datetime.fromisoformat(str(row.get("event_date") or ""))
        except ValueError:
            problems.append(f"{label}: accepted test timestamp required")
    return "; ".join(problems) or None
