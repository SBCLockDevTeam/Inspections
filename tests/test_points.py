from datetime import datetime

from alarm_inspection.domain.points import decide_point, first_event_by_point, normalize_point
from alarm_inspection.intake.event_history import normalize_rows as normalize_event_rows
from alarm_inspection.intake.points_list import normalize_rows


def test_normalize_point_accepts_common_formats():
    assert normalize_point("Point 2") == 2
    assert normalize_point("PT  17") == 17
    assert normalize_point("P200") == 200
    assert normalize_point(17.0) == 17
    assert normalize_point("not a point") is None


def test_normalize_rows_keeps_excel_numeric_point_values():
    rows = normalize_rows([["Point Number", "Description"], [17.0, "Smoke detector"]])
    assert rows[0].address == 17
    assert rows[0].accepted is True


def test_normalize_rows_keeps_unassigned_points_for_review():
    rows = normalize_rows([["Point", "Description"], ["Unassigned", "Door contact"]])
    assert len(rows) == 1
    assert rows[0].accepted is False
    assert rows[0].text == "Door contact"


def test_normalize_rows_appends_wrapped_text_to_previous_point():
    rows = normalize_rows(
        [
            ["Point", "Description"],
            ["Point 2", "Main Entry"],
            [None, "West Door"],
            ["Point 3", "Lobby Motion"],
        ]
    )
    assert len(rows) == 2
    assert rows[0].address == 2
    assert rows[0].text == "Main Entry West Door"
    assert rows[1].address == 3
    assert rows[1].text == "Lobby Motion"


def test_normalize_rows_does_not_attach_orphan_text_to_next_point():
    rows = normalize_rows(
        [
            ["Point", "Description"],
            [None, "Site Notes"],
            ["Point 4", "Office Door"],
        ]
    )
    assert len(rows) == 2
    assert rows[0].address is None
    assert rows[0].accepted is False
    assert rows[0].text == "Site Notes"
    assert rows[1].address == 4
    assert rows[1].text == "Office Door"


def test_decision_rejects_unassigned_and_out_of_range_rows():
    assert not decide_point({"point": "Point 2", "text": "unassigned"}).accepted
    assert not decide_point({"point": "Point 256", "text": "Motion"}).accepted
    assert decide_point({"point": "Point 2", "text": "RX Wall Motion"}).accepted


def test_first_event_by_point_selects_earliest_a_or_t():
    events = [
        {"point": "2", "event_type": "A", "timestamp": datetime(2026, 1, 1, 12, 5)},
        {"point": "Point 2", "event_type": "T", "timestamp": datetime(2026, 1, 1, 12, 1)},
        {"point": "3", "event_type": "X", "timestamp": datetime(2026, 1, 1, 12, 0)},
    ]
    assert first_event_by_point(events)[2] == datetime(2026, 1, 1, 12, 1)
    assert 3 not in first_event_by_point(events)


def test_event_history_normalize_rows_keeps_only_a_t_and_earliest_per_point():
    rows = [
        ["Date", "Zone", "State", "Extra"],
        ["2026-01-02 10:00", "6", "A", "ignore"],
        ["2026-01-02 09:00", "Point 6", "T", "ignore"],
        ["2026-01-02 08:00", "6", "R", "ignore"],
        ["2026-01-02 11:00", "7", "A", "ignore"],
    ]
    result = normalize_event_rows(rows)
    assert result[6] == datetime(2026, 1, 2, 9, 0)
    assert result[7] == datetime(2026, 1, 2, 11, 0)
    assert len(result) == 2


def test_event_history_normalize_rows_detects_alias_columns():
    rows = [
        ["Timestamp", "Point #", "Event Type"],
        ["2026-01-03 08:30", "PT 9", "A"],
    ]
    result = normalize_event_rows(rows)
    assert result[9] == datetime(2026, 1, 3, 8, 30)

