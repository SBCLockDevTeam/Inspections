from datetime import date

from alarm_inspection.api.pdf_export import (
    build_default_nfpa_draft,
    build_nfpa_draft_filename,
    build_report_filename,
    normalize_export_rows,
    normalize_nfpa_draft_fields,
    validate_export_rows,
)


def test_build_report_filename_uses_required_pattern():
    filename = build_report_filename(
        store_number="4388",
        address="123 Main St, Waynesboro, VA",
        category="Gas Station",
        completion_date=date(2026, 9, 22),
    )
    assert filename == "4388-Waynesboro,VA-Initiating Devices-Gas Station-09-22-26.pdf"


def test_normalize_export_rows_keeps_expected_fields():
    rows = normalize_export_rows(
        [
            {
                "text": "Smoke",
                "address": 4,
                "location": "Front Entry",
                "event_date": "2026-09-22 08:05:00",
            }
        ]
    )
    assert rows == [
        {
            "text": "Smoke",
            "address": "4",
            "location": "Front Entry",
            "event_date": "2026-09-22 08:05:00",
        }
    ]


def test_validate_export_rows_allows_partial_rows():
    assert validate_export_rows([
        {"text": "Smoke", "address": "2", "location": "", "event_date": "2026-09-22 08:05:00"}
    ]) is None

    assert validate_export_rows([
        {"text": "Smoke", "address": "2", "location": "Front", "event_date": "2026-09-22 (pending)"}
    ]) is None


def test_build_nfpa_draft_filename_uses_required_pattern():
    filename = build_nfpa_draft_filename(
        store_number="4388",
        address="123 Main St, Waynesboro, VA",
        completion_date=date(2026, 9, 22),
    )
    assert filename == "4388-Waynesboro,VA-NFPA72-Editable-09-22-26.pdf"


def test_normalize_nfpa_draft_fields_merges_defaults_and_filters_unknown_keys():
    defaults = build_default_nfpa_draft(store_number="1", address="A", inspector_name="Tech")
    normalized = normalize_nfpa_draft_fields(
        {
            "property_name": "Walmart Supercenter",
            "unknown_key": "ignored",
            "store_number": 1234,
        },
        defaults,
    )
    assert normalized["property_name"] == "Walmart Supercenter"
    assert normalized["store_number"] == "1234"
    assert "unknown_key" not in normalized
    assert normalized["property_address"] == "A"
