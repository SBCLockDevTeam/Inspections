"""Deterministic Event History normalization."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
import re
from typing import Iterable

from alarm_inspection.domain.points import first_event_by_point, normalize_point


def _header_score(value: object, aliases: set[str]) -> int:
    normalized = "" if value is None else re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())
    normalized_aliases = {re.sub(r"[^a-z0-9]+", "", alias.lower()) for alias in aliases}
    return 1 if normalized in normalized_aliases else 0


def detect_columns(rows: list[list[object]]) -> tuple[int, int, int, int]:
    """Return header row, date column, zone column, and state column indexes."""
    date_aliases = {"date", "datetime", "time", "timestamp", "event date", "event time"}
    zone_aliases = {"zone", "point", "point number", "point #", "address", "device address"}
    state_aliases = {"state", "event type", "type", "status"}

    best = (-1, 0, 0, 0, 0)
    for row_index, row in enumerate(rows[:30]):
        for date_index, date_value in enumerate(row):
            for zone_index, zone_value in enumerate(row):
                for state_index, state_value in enumerate(row):
                    score = (
                        _header_score(date_value, date_aliases)
                        + _header_score(zone_value, zone_aliases)
                        + _header_score(state_value, state_aliases)
                    )
                    if score > best[0]:
                        best = (score, row_index, date_index, zone_index, state_index)
    if best[0] < 3:
        raise ValueError("Could not identify Date, Zone, and State columns")
    return best[1], best[2], best[3], best[4]


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)

    text = str(value).strip()
    if not text:
        return None

    parsers = (
        datetime.fromisoformat,
        lambda raw: datetime.strptime(raw, "%m/%d/%Y %H:%M:%S"),
        lambda raw: datetime.strptime(raw, "%m/%d/%Y %H:%M"),
        lambda raw: datetime.strptime(raw, "%m/%d/%Y"),
        lambda raw: datetime.strptime(raw, "%Y-%m-%d %H:%M:%S"),
        lambda raw: datetime.strptime(raw, "%Y-%m-%d %H:%M"),
        lambda raw: datetime.strptime(raw, "%Y-%m-%d"),
    )
    for parser in parsers:
        try:
            return parser(text)
        except ValueError:
            continue
    return None


def normalize_rows(rows: Iterable[list[object]]) -> dict[int, datetime]:
    materialized = list(rows)
    header_row, date_col, zone_col, state_col = detect_columns(materialized)
    events: list[dict[str, object]] = []

    for row in materialized[header_row + 1 :]:
        date_value = row[date_col] if date_col < len(row) else None
        zone_value = row[zone_col] if zone_col < len(row) else None
        state_value = row[state_col] if state_col < len(row) else None

        timestamp = _parse_timestamp(date_value)
        if timestamp is None:
            continue

        state = "" if state_value is None else str(state_value).strip().upper()
        if state not in {"A", "T"}:
            continue

        point = normalize_point(zone_value)
        if point is None:
            continue

        events.append({"event_type": state, "point": point, "timestamp": timestamp})

    earliest = first_event_by_point(events)
    return {int(point): timestamp for point, timestamp in earliest.items() if isinstance(timestamp, datetime)}


def parse_xlsx(path: str | Path) -> dict[int, datetime]:
    """Read the first usable worksheet and return earliest qualifying event per point."""
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    last_error: ValueError | None = None
    for worksheet in workbook.worksheets:
        rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
        try:
            normalized = normalize_rows(rows)
        except ValueError as exc:
            last_error = exc
            continue
        if normalized:
            return normalized
    raise last_error or ValueError("No qualifying Event History rows were found in the workbook")