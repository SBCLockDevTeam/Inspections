"""Deterministic XLSX Points List normalization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Iterable

from alarm_inspection.domain.points import decide_point, normalize_point


@dataclass(frozen=True)
class NormalizedPoint:
    address: int | None
    text: str
    accepted: bool
    reason: str
    source_row: int


def _header_score(value: object, aliases: set[str]) -> int:
    normalized = "" if value is None else re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())
    aliases = {re.sub(r"[^a-z0-9]+", "", alias.lower()) for alias in aliases}
    return 1 if normalized in aliases else 0


def detect_columns(rows: list[list[object]]) -> tuple[int, int, int]:
    """Return header row, point column, and text column indexes."""
    point_aliases = {
        "point", "points", "point assignment", "point assignments", "point number",
        "point numbers", "point #", "point no", "point id", "address", "device address",
    }
    text_aliases = {"text", "point text", "description", "device", "device type", "device description"}
    best = (-1, 0, 0, 0)
    for row_index, row in enumerate(rows[:30]):
        for point_index, value in enumerate(row):
            for text_index, text_value in enumerate(row):
                score = _header_score(value, point_aliases) + _header_score(text_value, text_aliases)
                if score > best[0]:
                    best = (score, row_index, point_index, text_index)
    if best[0] < 2:
        raise ValueError("Could not identify point and text columns")
    return best[1], best[2], best[3]


def normalize_rows(rows: Iterable[list[object]]) -> list[NormalizedPoint]:
    materialized = list(rows)
    header_row, point_col, text_col = detect_columns(materialized)
    output_rows: list[dict[str, object]] = []
    orphan_text: list[str] = []
    orphan_start_row: int | None = None
    current_point_index: int | None = None

    def flush_orphan_text() -> None:
        nonlocal orphan_start_row
        if not orphan_text:
            return
        output_rows.append({
            "point": None,
            "text": " ".join(orphan_text),
            "source_row": orphan_start_row if orphan_start_row is not None else len(materialized),
        })
        orphan_text.clear()
        orphan_start_row = None

    for row_number, row in enumerate(materialized[header_row + 1 :], header_row + 2):
        point_value = row[point_col] if point_col < len(row) else None
        text_value = row[text_col] if text_col < len(row) else None
        text = "" if text_value is None else str(text_value).strip()
        address = normalize_point(point_value)

        if point_value not in (None, ""):
            flush_orphan_text()
            output_rows.append({"point": point_value, "text": text, "source_row": row_number})
            current_point_index = None
            if address is not None and 1 <= address <= 255:
                current_point_index = len(output_rows) - 1
            continue

        if text:
            if current_point_index is not None:
                existing = str(output_rows[current_point_index]["text"] or "").strip()
                output_rows[current_point_index]["text"] = " ".join(
                    part for part in [existing, text] if part
                )
            else:
                if orphan_start_row is None:
                    orphan_start_row = row_number
                orphan_text.append(text)
            continue

        # Blank row creates a structural boundary for continuation text.
        flush_orphan_text()
        current_point_index = None

    flush_orphan_text()

    output: list[NormalizedPoint] = []
    for item in output_rows:
        decision = decide_point({"point": item["point"], "text": item["text"]})
        output.append(
            NormalizedPoint(
                decision.address,
                str(item["text"]),
                decision.accepted,
                decision.reason,
                int(item["source_row"]),
            )
        )
    return output


def parse_xlsx(path: str | Path) -> list[dict]:
    """Read the first usable worksheet and return normalized decisions."""
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
            return [asdict(item) for item in normalized]
    raise last_error or ValueError("No point rows were found in the workbook")

