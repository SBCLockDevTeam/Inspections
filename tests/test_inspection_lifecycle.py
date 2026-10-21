"""Saving and deleting inspections must preserve lifecycle and audit boundaries."""
import pytest
pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from alarm_inspection.storage import Inspection, SourceFile, PointListDecision, PointListEventDate
from datetime import datetime, timezone


@pytest.fixture
def inspection_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'inspection.db'}")
    from alarm_inspection.api.app import create_app
    from alarm_inspection.storage import open_store

    client = TestClient(create_app())
    response = client.post("/api/auth/login", json={
        "email": "john.porter@securitybuildingcontrols.com", "password": "password",
    })
    assert response.status_code == 200
    return client, open_store(), tmp_path


def new_inspection():
    return dict(store_number="1234", address="Test address", store_type="Walmart - Supercenter",
                inspector_name="Test Inspector", start_date="2026-10-21", completion_date="2026-10-22")


def test_save_creates_one_complete_inspection_and_rejects_duplicate(inspection_app):
    client, _, _ = inspection_app
    assert client.get("/api/inspections").json() == []
    saved = client.post("/api/inspections/blank", json=new_inspection()).json()
    assert "id" in saved
    details = client.get(f"/api/inspections/{saved['id']}").json()
    for field, value in new_inspection().items():
        assert details[field] == value
    assert "error" in client.post("/api/inspections/blank", json=new_inspection()).json()
    assert len(client.get("/api/inspections").json()) == 1


@pytest.mark.parametrize("changes", [{"store_number": " "}, {"address": ""},
                                      {"completion_date": "2026-10-20"}])
def test_invalid_save_adds_nothing(inspection_app, changes):
    client, _, _ = inspection_app
    assert client.post("/api/inspections/blank", json=new_inspection() | changes).status_code == 422
    assert client.get("/api/inspections").json() == []


def test_delete_hides_inspection_preserves_audit_and_blocks_changes(inspection_app):
    client, store, tmp_path = inspection_app
    inspection_id = client.post("/api/inspections/blank", json=new_inspection()).json()["id"]
    original = tmp_path / "original.xlsx"
    original.write_bytes(b"audit source")
    with store.begin() as session:
        session.add(SourceFile(id="source", inspection_id=inspection_id, filename=original.name,
                               path=str(original), kind="points_list"))
        session.add(PointListDecision(id="decision", inspection_id=inspection_id, point_list_id="panel",
                                      address=1, text="Door", accepted=True, deleted=False))
        session.add(PointListEventDate(id="mapping", inspection_id=inspection_id, point_list_id="panel",
                                      point_address=1, event_timestamp=datetime.now(timezone.utc)))
    assert client.delete(f"/api/inspections/{inspection_id}").json()["status"] == "deleted"
    assert client.get("/api/inspections").json() == []
    assert client.get(f"/api/inspections/{inspection_id}").status_code == 404
    assert client.patch(f"/api/inspections/{inspection_id}", json={"address": "changed"}).status_code == 404
    assert client.post(f"/api/inspections/{inspection_id}/export-pdf", json={}).status_code == 404
    with store() as session:
        assert session.get(Inspection, inspection_id).status == "deleted"
        assert session.get(SourceFile, "source") is not None
        assert session.get(PointListDecision, "decision").accepted
        assert session.get(PointListEventDate, "mapping") is not None
    assert original.read_bytes() == b"audit source"
    # A deleted inspection no longer conflicts with a new inspection for that store/date.
    assert "id" in client.post("/api/inspections/blank", json=new_inspection()).json()
