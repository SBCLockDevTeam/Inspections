"""Synthetic print-report layouts; customer workbooks stay outside the repo."""
from openpyxl import Workbook

from alarm_inspection.intake.points_list import detect_columns, normalize_rows, parse_xlsx


def report_headers():
    return [
        ["POINT", None, "Point", None, "Area"],
        ["ASSIGNMENTS", "Point Text", "Index", "Point Index Description", "Assign"],
    ]


def test_wrapped_headers_use_address_column_instead_of_point_index(tmp_path):
    book = Workbook()
    sheet = book.active
    for row in [["Point Assignment Report"], *report_headers(),
                ["Point 17", "Smoke detector", 2], [None, "West hall"],
                ["Point 18", " ", 0, "Unassigned"]]:
        sheet.append(row)
    path = tmp_path / "report.xlsx"
    book.save(path)
    rows = parse_xlsx(path)
    assert [(r["address"], r["text"], r["accepted"]) for r in rows] == [
        (17, "Smoke detector West hall", True), (None, "", False),
    ]
    assert rows[0]["source_row"] == 4


def test_page_furniture_and_repeated_wrapped_headers_are_boundaries():
    rows = normalize_rows([
        *report_headers(), ["Point 2", "Entry"],
        ["Report timestamp", None, "Page", 1, "of", 2],
        ["Account Number :", "Example"], ["Point Assignment Report"],
        *report_headers(), [None, "Orphan note"], ["Point 3", "Motion"],
        ["Report timestamp", None, "Page", 2, "of", 2],
    ])
    assert [(r.address, r.text, r.accepted) for r in rows] == [
        (2, "Entry", True), (None, "Orphan note", False), (3, "Motion", True),
    ]
    assert rows[-1].source_row == 10


def test_repeated_single_row_headers_are_skipped():
    rows = normalize_rows([
        ["Point", None, "Description"], [2, None, "Entry"],
        ["Point", None, "Description"], [3, None, "Motion"],
    ])
    assert [(r.address, r.text) for r in rows] == [(2, "Entry"), (3, "Motion")]


def test_header_columns_must_be_distinct():
    assert detect_columns([["Description", None, "Point #"], ["Smoke", None, 4]]) == (0, 2, 0)
