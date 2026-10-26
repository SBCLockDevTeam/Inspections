"""Header layout compatibility for the linear Event History detector."""
from datetime import datetime

import pytest
from openpyxl import Workbook

from alarm_inspection.intake.event_history import detect_columns, parse_xlsx


@pytest.mark.parametrize('headers, expected', [
    (['Date', 'Zone', 'State'], (0, 0, 1, 2)),
    ([' Event-Type ', None, 'DEVICE ADDRESS', 'Event.Date'], (0, 3, 2, 0)),
    (['status', '', 'point #', '', 'timestamp'], (0, 4, 2, 0)),
    (['Time', 'Point Number', 'Type'], (0, 0, 1, 2)),
    (['DateTime', 'Point', 'State'], (0, 0, 1, 2)),
    (['Event Time', 'Address', 'Status'], (0, 0, 1, 2)),
    (['Date', 'Timestamp', 'Point', 'Zone', 'State', 'Type'], (0, 0, 2, 4)),
])
def test_aliases_punctuation_order_and_duplicate_columns(headers, expected):
    assert detect_columns([headers]) == expected


def test_first_complete_row_wins_over_partial_and_later_headers():
    rows = [[], ['Report title'], ['Date', 'Zone'],
            ['State', None, 'Point', 'Date'], ['Date', 'Zone', 'State']]
    assert detect_columns(rows) == (3, 3, 2, 0)


def test_headers_must_be_on_the_same_row():
    with pytest.raises(ValueError, match='Could not identify Date, Zone, and State columns'):
        detect_columns([['Date'], ['Zone'], ['State']])


@pytest.mark.parametrize('rows', [[], [['Date', 'Zone']], [[None, '', 123]],
                                  [[] for _ in range(30)] + [['Date', 'Zone', 'State']]])
def test_missing_headers_and_original_search_limit(rows):
    with pytest.raises(ValueError, match='Could not identify Date, Zone, and State columns'):
        detect_columns(rows)


def test_header_at_last_allowed_row_with_wide_blank_columns():
    headers = [None] * 256
    headers[3], headers[127], headers[255] = 'State', 'Point #', 'Date'
    assert detect_columns([[] for _ in range(29)] + [headers]) == (29, 255, 127, 3)


def test_xlsx_sheet_fallback_and_event_checks_are_preserved(tmp_path):
    book = Workbook()
    book.active.append(['Date', 'Point'])  # Missing event type: try the next sheet.
    sheet = book.create_sheet('History')
    sheet.append(['Report title'])
    sheet.append(['Status', None, 'Device Address', None, 'Event Date'])
    sheet.append(['A', None, 'P2', None, '2026-10-01 12:00'])
    sheet.append(['T', None, 'Point 2', None, '2026-10-01 10:00'])
    sheet.append(['X', None, 'P2', None, '2026-10-01 08:00'])
    sheet.append(['A', None, 'wrong', None, '2026-10-01 09:00'])
    sheet.append(['T', None, 'P3', None, 'bad date'])
    sheet.append(['A', None, 'P4', None, '2026-10-01 11:00'])
    path = tmp_path / 'events.xlsx'
    book.save(path)
    assert parse_xlsx(path) == {2: datetime(2026, 10, 1, 10), 4: datetime(2026, 10, 1, 11)}
