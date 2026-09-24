from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from alarm_inspection.api.pdf_templates import normalize_template_field_values
from alarm_inspection.storage import Inspection, InspectionPdfTemplateDraft, SourceFile


def resolve_official_nfpa_template_path() -> Path | None:
    env_candidate = os.getenv("NFPA_TEMPLATE_PATH", "").strip()
    repo_root = Path(__file__).resolve().parents[4]
    candidates = [
        Path(env_candidate) if env_candidate else None,
        repo_root / "docs" / "NFPA72_template.pdf",
        repo_root / "docs" / "templates" / "NFPA72_template.pdf",
        repo_root / "infra" / "templates" / "NFPA72_template.pdf",
    ]
    for candidate in candidates:
        if candidate and candidate.exists() and candidate.is_file():
            return candidate
    return None


def latest_saved_nfpa_pdf_path(session, inspection_id: str) -> tuple[Path | None, str]:
    latest = (
        session.query(SourceFile)
        .filter(
            SourceFile.inspection_id == inspection_id,
            SourceFile.kind == "nfpa_template_draft",
        )
        .order_by(SourceFile.filename.desc())
        .first()
    )
    if latest is None:
        return None, ""
    path = Path(latest.path)
    if not path.exists() or not path.is_file():
        return None, ""
    return path, latest.filename


def load_template_draft_values(
    session,
    inspection_id: str,
    template_key: str,
    allowed_fields: list[str],
) -> dict[str, str]:
    row = (
        session.query(InspectionPdfTemplateDraft)
        .filter(
            InspectionPdfTemplateDraft.inspection_id == inspection_id,
            InspectionPdfTemplateDraft.template_key == template_key,
        )
        .first()
    )
    if row is None:
        return {name: "" for name in allowed_fields}
    try:
        parsed = json.loads(row.fields_json or "{}")
    except json.JSONDecodeError:
        parsed = {}
    return normalize_template_field_values(parsed, allowed_fields)


def find_inspection_identity_conflict(
    session,
    store_type_value: str,
    store_number_value: str,
    inspection_date_value: date,
    exclude_inspection_id: str | None = None,
) -> str | None:
    normalized_type = (store_type_value or "").strip().lower()
    normalized_number = (store_number_value or "").strip().lower()
    if not normalized_type or not normalized_number:
        return None

    candidates = (
        session.query(Inspection)
        .filter(Inspection.start_date == inspection_date_value)
        .all()
    )
    for candidate in candidates:
        if exclude_inspection_id and candidate.id == exclude_inspection_id:
            continue
        if (candidate.store_type or "").strip().lower() != normalized_type:
            continue
        if (candidate.store_number or "").strip().lower() != normalized_number:
            continue
        return candidate.id
    return None
