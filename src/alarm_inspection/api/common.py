from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

UPLOAD_ROOT = Path("/tmp/alarm-inspection-uploads")


def as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off", ""}:
        return False
    return default


def format_event_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%d %H:%M:%S")


def parse_saved_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text, text.replace(" ", "T", 1)):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def parse_date_value(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def event_history_kind(point_list_id: str | None) -> str:
    if not point_list_id:
        return "event_history"
    # Keep kind within the existing varchar(40) limit in production DB.
    return f"event_history:{point_list_id[:12]}"


def ensure_inspection_upload_dir(inspection_id: str) -> Path:
    upload_dir = UPLOAD_ROOT / inspection_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir
