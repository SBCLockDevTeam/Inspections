from datetime import date

import pytest

from alarm_inspection.domain.inspection_names import build_inspection_name, location_from_address


@pytest.mark.parametrize("address, expected", [
    ("123 Main Street, Virginia Beach, VA 23456", ("Virginia Beach", "VA")),
    ("2021 LYNNHAVEN PKWY #L VIRGINIA BEACH, VA 23456", ("Virginia Beach", "VA")),
    ("1170 N MILITARY HWY NORFOLK, VA 23502", ("Norfolk", "VA")),
    ("1098 FREDRICK BLVD #L Portsmouth, VA 23707", ("Portsmouth", "VA")),
    ("1720 E LITTLE CREEK RD NORFOLK, VA 23518, US", ("Norfolk", "VA")),
    ("waynesboro,va", ("Waynesboro", "VA")),
    ("Roanoke", ("Roanoke", "")),
    ("123 Main Street", ("", "")),
    ("", ("", "")),
])
def test_conservative_legacy_location_extraction(address, expected):
    assert location_from_address(address) == expected


def test_name_preserves_store_number_and_uses_start_month():
    assert build_inspection_name(" 0042 ", "virginia beach", "va", date(2027, 1, 31)) == "0042-Virginia Beach-VA-01-2027"


def test_migration_is_idempotent_and_preserves_explicit_locations(tmp_path, monkeypatch):
    pytest.importorskip("sqlalchemy")
    from sqlalchemy import create_engine, text
    from alarm_inspection.storage import open_store, Inspection

    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(text("""CREATE TABLE inspections (
            id VARCHAR(36) PRIMARY KEY, store_number VARCHAR(100), address VARCHAR(500),
            store_type VARCHAR(80), inspector_name VARCHAR(120), start_date DATE,
            completion_date DATE, status VARCHAR(40), created_at DATETIME)"""))
        c.execute(text("""INSERT INTO inspections VALUES ('legacy','0042',
            '123 Main St, Norfolk, VA 23502', 'Walmart - Supercenter', 'Tech',
            '2026-09-21','2026-09-22','pending_event_history','2026-09-21 12:00:00')"""))
    monkeypatch.setenv("DATABASE_URL", url)
    store = open_store()
    with store.begin() as session:
        row = session.get(Inspection, "legacy")
        assert row.name == "0042-Norfolk-VA-09-2026"
        assert row.address == "123 Main St, Norfolk, VA 23502"
        row.city = "Virginia Beach"
    store = open_store()
    with store() as session:
        assert session.get(Inspection, "legacy").name == "0042-Virginia Beach-VA-09-2026"
