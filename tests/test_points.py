from datetime import datetime

from alarm_inspection.domain.points import decide_point, first_event_by_point, normalize_point


def test_normalize_point_accepts_common_formats():
    assert normalize_point("Point 2") == 2
    assert normalize_point("PT  17") == 17
    assert normalize_point("P200") == 200
    assert normalize_point("not a point") is None


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

