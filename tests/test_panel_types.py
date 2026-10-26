"""Panel type administration, persistence, and intake enforcement."""
from datetime import datetime, timezone
from io import BytesIO
import json
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from openpyxl import Workbook
from alarm_inspection.storage import PanelType, PointList, User


@pytest.fixture
def panel_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'panels.db'}")
    from alarm_inspection.api.app import create_app
    from alarm_inspection.api import common
    from alarm_inspection.api.routers import point_lists, inspections
    from alarm_inspection.storage import open_store
    for module in (common, point_lists, inspections):
        monkeypatch.setattr(module, "UPLOAD_ROOT", tmp_path / "uploads")
    client = TestClient(create_app())
    assert client.post("/api/auth/login", json={"email": "john.porter@securitybuildingcontrols.com", "password": "TestBootstrapPassword42!"}).status_code == 200
    client.post("/api/auth/reset-password", json={"current_password": "TestBootstrapPassword42!", "new_password": "TestBootstrapPassword42!"})
    return client, open_store()


def workbook_bytes():
    book = Workbook()
    book.active.append(["Point", "Description"])
    book.active.append([1, "Front Door"])
    target = BytesIO()
    book.save(target)
    return target.getvalue()


def inspection_payload():
    return dict(store_number="0042", address="123 Test St", city="Norfolk", state="VA", start_date="2026-10-01", completion_date="2026-10-02")


def test_defaults_and_new_types_persist_without_duplicates(panel_app):
    client, store = panel_app
    from alarm_inspection.api.app import create_app
    assert {p["name"] for p in client.get("/api/point-lists/types").json()["panel_types"]} == {"Combo", "Fire", "Burglar", "Gas Station"}
    added = client.post("/api/admin/panel-types", json={"name": "  Medical   Alarm  "})
    assert added.status_code == 201
    assert added.json()["panel_type"]["name"] == "Medical Alarm"
    assert client.post("/api/admin/panel-types", json={"name": "medical alarm"}).status_code == 409
    create_app()
    with store() as session:
        assert session.query(PanelType).count() == 5
        assert session.get(PanelType, added.json()["panel_type"]["id"]).name == "Medical Alarm"


@pytest.mark.parametrize("name", ["", " \t ", "x" * 41, None, ["Fire"]])
def test_invalid_names_add_nothing(panel_app, name):
    client, store = panel_app
    assert client.post("/api/admin/panel-types", json={"name": name}).status_code == 400
    with store() as session:
        assert session.query(PanelType).count() == 4


def test_technicians_can_read_but_cannot_add_types(panel_app):
    client, store = panel_app
    from alarm_inspection.api.security import password_record
    with store.begin() as session:
        session.add(User(id=str(uuid4()), email="tech@example.invalid", password_hash=password_record("TestPassword"), is_admin=False, force_password_reset=False, is_active=True, created_at=datetime.now(timezone.utc)))
    client.post("/api/auth/login", json={"email": "tech@example.invalid", "password": "TestPassword"})
    assert client.get("/api/point-lists/types").status_code == 200
    assert client.post("/api/admin/panel-types", json={"name": "Medical"}).status_code == 403
    client.post("/api/auth/logout")
    assert client.get("/api/point-lists/types").status_code == 401
    assert client.post("/api/admin/panel-types", json={"name": "Medical"}).status_code == 401


def test_new_type_works_through_review_and_approval(panel_app):
    client, store = panel_app
    client.post("/api/admin/panel-types", json={"name": "Medical Alarm"})
    inspection_id = client.post("/api/inspections/blank", json=inspection_payload()).json()["id"]
    preview = client.post("/api/point-lists/preview", data={"point_list_categories": "Medical Alarm"}, files=[("points_files", ("points.xlsx", workbook_bytes()))]).json()
    assert preview["lists"][0]["category"] == "Medical Alarm"
    result = client.post(f"/api/inspections/{inspection_id}/point-lists", data={"point_list_category": "Medical Alarm", "point_decisions": json.dumps(preview["rows"])}, files={"points_file": ("points.xlsx", workbook_bytes())}).json()
    assert result["status"] == "saved"
    details = client.get(f"/api/inspections/{inspection_id}").json()
    assert details["point_lists"][0]["category"] == "Medical Alarm"
    assert details["accepted_points"][0]["text"] == "Front Door"
    with store() as session:
        assert session.query(PointList).one().category == "Medical Alarm"


def test_unconfigured_type_is_rejected_by_all_intake_endpoints(panel_app):
    client, store = panel_app
    inspection_id = client.post("/api/inspections/blank", json=inspection_payload()).json()["id"]
    decisions = json.dumps([dict(address=1, text="Door", accepted=True)])
    result = client.post(f"/api/inspections/{inspection_id}/point-lists", data={"point_list_category": "Unconfigured", "point_decisions": decisions}, files={"points_file": ("points.xlsx", workbook_bytes())})
    assert "error" in result.json()
    assert "error" in client.post("/api/point-lists/preview", data={"point_list_categories": "Unconfigured"}, files=[("points_files", ("points.xlsx", workbook_bytes()))]).json()
    assert "error" in client.post("/api/inspections", data={"store_number": "43", "address": "Test", "city": "Norfolk", "state": "VA", "point_list_categories": "Unconfigured", "point_decisions": decisions}, files=[("points_files", ("points.xlsx", workbook_bytes()))]).json()
    with store() as session:
        assert session.query(PointList).count() == 0


def test_startup_preserves_legacy_categories(panel_app):
    client, store = panel_app
    from alarm_inspection.api.app import create_app
    with store.begin() as session:
        session.add(PointList(id="legacy", inspection_id="existing", category="Elevator Alarm", filename="original.xlsx", path="/original.xlsx", accepted_at=datetime.now(timezone.utc)))
    create_app()
    assert "Elevator Alarm" in {p["name"] for p in client.get("/api/point-lists/types").json()["panel_types"]}
    with store() as session:
        assert session.get(PointList, "legacy").filename == "original.xlsx"
        assert session.get(PointList, "legacy").category == "Elevator Alarm"
