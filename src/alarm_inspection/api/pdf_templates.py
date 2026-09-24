from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


_TEMPLATE_REGISTRY: dict[str, dict[str, str]] = {
    "nfpa72": {
        "label": "NFPA 72 System Record",
        "default_filename": "NFPA72_template.pdf",
        "env_var": "NFPA_TEMPLATE_PATH",
        "fallback_relative": "docs/templates/NFPA72_template.pdf",
    }
}


def list_templates() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for key, item in _TEMPLATE_REGISTRY.items():
        items.append({"key": key, "label": item["label"]})
    return items


def template_meta(template_key: str) -> dict[str, str] | None:
    return _TEMPLATE_REGISTRY.get(template_key)


def resolve_template_path(template_key: str, env_lookup: dict[str, str] | None = None) -> Path | None:
    meta = template_meta(template_key)
    if meta is None:
        return None

    env = env_lookup or {}
    env_var = meta["env_var"]
    env_candidate = (env.get(env_var) or "").strip()
    if env_candidate:
        p = Path(env_candidate)
        if p.exists() and p.is_file():
            return p

    fallback = _repo_root() / meta["fallback_relative"]
    if fallback.exists() and fallback.is_file():
        return fallback
    return None


def extract_template_fields(template_path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Template editing requires pypdf. Install web dependencies including pypdf.") from exc

    reader = PdfReader(str(template_path))
    fields = reader.get_fields() or {}
    return sorted(str(name) for name in fields.keys())


def normalize_template_field_values(raw_fields: object, allowed_fields: list[str]) -> dict[str, str]:
    allowed = {str(name) for name in allowed_fields}
    normalized = {name: "" for name in allowed_fields}
    if not isinstance(raw_fields, dict):
        return normalized

    for key, value in raw_fields.items():
        name = str(key)
        if name not in allowed:
            continue
        normalized[name] = str(value or "").strip()
    return normalized


def fill_template_pdf(template_path: Path, fields: dict[str, str]) -> bytes:
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import BooleanObject, NameObject
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Template editing requires pypdf. Install web dependencies including pypdf.") from exc

    reader = PdfReader(str(template_path))
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)

    for page in writer.pages:
        writer.update_page_form_field_values(page, fields, auto_regenerate=False)

    if "/AcroForm" in writer._root_object:  # pylint: disable=protected-access
        writer._root_object[NameObject("/AcroForm")][NameObject("/NeedAppearances")] = BooleanObject(True)  # pylint: disable=protected-access

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def default_template_download_name(template_key: str, store_number: str) -> str:
    clean_store = "".join(ch for ch in (store_number or "store") if ch.isalnum() or ch in {"-", "_"}).strip() or "store"
    return f"{clean_store}-{template_key}-updated.pdf"
