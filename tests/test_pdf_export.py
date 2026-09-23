from datetime import date

from alarm_inspection.api.pdf_export import (
    build_report_filename,
    normalize_export_rows,
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


def test_validate_export_rows_requires_location_and_final_result():
    assert validate_export_rows([
        {"text": "Smoke", "address": "2", "location": "", "event_date": "2026-09-22 08:05:00"}
    ]) == "Row 1 is missing Location."

    assert validate_export_rows([
        {"text": "Smoke", "address": "2", "location": "Front", "event_date": "2026-09-22 (pending)"}
    ]) == "Row 1 still has a pending Test Result. Accept results before exporting."
