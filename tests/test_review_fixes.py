"""Regression coverage for report completion, retained evidence, and secure bootstrap."""
from datetime import datetime
from io import BytesIO
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, text

from alarm_inspection.storage import (
    InspectionAuditEntry, PointList, PointListDecision, PointListEventDate,
    PointListPendingEventDate, SourceFile, User, UserSession, open_store,
)

PASSWORD = "TestBootstrapPassword42!"
ADMIN = "john.porter@securitybuildingcontrols.com"


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'review.db'}")
    from alarm_inspection.api import common
    from alarm_inspection.api.app import create_app
    monkeypatch.setattr(common, "UPLOAD_ROOT", tmp_path / "uploads")
    client = TestClient(create_app())
    assert client.post('/api/auth/login', json={'email': ADMIN, 'password': PASSWORD}).status_code == 200
    assert client.post('/api/auth/reset-password', json={'current_password': PASSWORD, 'new_password': PASSWORD}).status_code == 200
    inspection = client.post('/api/inspections/blank', json={
        'store_number': '123', 'address': '123 Main St', 'city': 'Norfolk', 'state': 'VA',
        'start_date': '2026-10-01', 'completion_date': '2026-10-02',
    }).json()['id']
    book = Workbook(); book.active.append(['Point', 'Text']); book.active.append([1, 'Smoke'])
    data = BytesIO(); book.save(data)
    panel = client.post(f'/api/inspections/{inspection}/point-lists', data={
        'point_list_category': 'Fire', 'point_decisions': json.dumps([
            {'address': 1, 'text': 'Smoke', 'location': 'Lobby', 'accepted': True},
            {'address': 2, 'text': 'Door', 'location': 'Entry', 'accepted': True},
        ]),
    }, files={'points_file': ('points.xlsx', data.getvalue())}).json()['point_list_id']
    store = open_store()
    with store() as session:
        user_id = session.query(User).one().id
        points = {p.address: p.id for p in session.query(PointListDecision).all()}
    return client, store, f'/api/inspections/{inspection}', panel, points, user_id


def accept(client, base, panel, points=(1, 2)):
    return client.post(base + '/event-dates/save', json={
        'point_list_id': panel, 'matches': [
            {'point': p, 'timestamp': '2026-10-01 10:00:00'} for p in points
        ],
    })


def test_export_requires_all_saved_results_and_cannot_be_forged(app_data):
    client, store, base, panel, points, _ = app_data
    payload = {'point_list_id': panel, 'rows': [
        {'address': '1', 'text': 'Forged', 'location': 'X', 'event_date': '2026-10-01 11:00:00'}
    ]}
    response = client.post(base + '/export-pdf', json=payload)
    assert response.status_code == 400 and 'Point 1' in response.json()['detail']
    accept(client, base, panel, (1,))
    response = client.post(base + '/export-pdf', json=payload)
    assert response.status_code == 400 and 'Point 2' in response.json()['detail']
    with store() as session:
        assert session.query(SourceFile).filter(SourceFile.kind.like('report_pdf:%')).count() == 0
    accept(client, base, panel, (2,))
    response = client.post(base + '/export-pdf', json=payload)
    assert response.status_code == 200 and response.content.startswith(b'%PDF')
    assert '123-Norfolk,VA-Initiating Devices-Fire-10-02-26.pdf' in response.headers['content-disposition']
    from pypdf import PdfReader
    content = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
    assert 'Smoke' in content and 'Door' in content and 'Forged' not in content


@pytest.mark.parametrize('problem', ['location', 'description', 'duplicate', 'review', 'empty', 'city', 'mapping_duplicate'])
def test_export_blocks_unresolved_saved_data(app_data, problem):
    client, store, base, panel, points, _ = app_data
    accept(client, base, panel)
    with store.begin() as session:
        point = session.get(PointListDecision, points[1])
        if problem == 'location': point.location = ''
        elif problem == 'description': point.text = ''
        elif problem == 'duplicate': point.address = 2
        elif problem == 'review': point.accepted = False
        elif problem == 'empty':
            session.query(PointListDecision).update({'deleted': True})
        elif problem == 'city':
            from alarm_inspection.storage import Inspection
            session.get(Inspection, base.rsplit('/', 1)[1]).city = ''
        elif problem == 'mapping_duplicate':
            session.add(PointListEventDate(id='duplicate', inspection_id=base.rsplit('/', 1)[1],
                point_list_id=panel, point_address=1, event_timestamp=datetime(2026, 10, 2, 12)))
    assert client.post(base + '/export-pdf', json={'point_list_id': panel}).status_code == 400


def test_stale_and_partial_table_saves_retain_mapping_identity_and_source(app_data):
    client, store, base, panel, points, _ = app_data
    with store.begin() as session:
        session.add(PointListPendingEventDate(
            inspection_id=base.rsplit('/', 1)[1], point_list_id=panel, point_address=1,
            event_timestamp=datetime(2026, 10, 1, 10), source_filename='original-history.xlsx',
        ))
    accept(client, base, panel)
    with store() as session:
        original = [(m.id, m.point_address, m.source_filename, m.event_timestamp)
                    for m in session.query(PointListEventDate).order_by(PointListEventDate.point_address)]
        assert original[0][2] == 'original-history.xlsx'
    # A stale browser can save a description without deleting a newer accepted event.
    result = client.post(base + '/accepted-points/save', json={'point_list_id': panel, 'rows': [
        {'id': points[1], 'text': 'Edited Smoke', 'event_date': ''},
    ]})
    assert result.status_code == 200
    assert client.post(base + '/accepted-points/save', json={'point_list_id': panel, 'rows': []}).status_code == 200
    with store() as session:
        assert original == [(m.id, m.point_address, m.source_filename, m.event_timestamp)
                            for m in session.query(PointListEventDate).order_by(PointListEventDate.point_address)]
        audit = session.query(InspectionAuditEntry).filter_by(action='point_edited').one()
        assert json.loads(audit.details_json)['before']['text'] == 'Smoke'
        assert json.loads(audit.details_json)['after']['text'] == 'Edited Smoke'


@pytest.mark.parametrize('change', [{'event_date': '2026-10-02 15:00:00'}, {'address': 3}])
def test_mapped_point_corrections_require_explicit_clear_and_roll_back(app_data, change):
    client, store, base, panel, points, _ = app_data
    accept(client, base, panel)
    response = client.post(base + '/accepted-points/save', json={'point_list_id': panel, 'rows': [
        {'id': points[1], 'text': 'Must roll back', **change},
    ]})
    assert response.status_code == 409
    with store() as session:
        assert session.get(PointListDecision, points[1]).text == 'Smoke'
        assert session.query(PointListEventDate).count() == 2


def test_clear_requires_confirmation_and_retains_previous_results_in_audit(app_data):
    client, store, base, panel, points, user_id = app_data
    accept(client, base, panel)
    assert client.post(base + '/event-dates/clear', json={'point_list_id': panel}).status_code == 400
    with store() as session:
        assert session.query(PointListEventDate).count() == 2
    result = client.post(base + '/event-dates/clear', json={'point_list_id': panel, 'confirmed': True})
    assert result.json()['cleared'] == 2
    with store() as session:
        assert session.query(PointListEventDate).count() == 0
        audit = session.query(InspectionAuditEntry).filter_by(action='event_results_cleared').one()
        assert audit.decided_by == user_id
        assert {row['point'] for row in json.loads(audit.details_json)} == {1, 2}
    # After the explicit correction action the technician can enter revised results.
    assert client.post(base + '/accepted-points/save', json={'point_list_id': panel, 'rows': [
        {'id': points[1], 'event_date': '2026-10-02 11:00:00'},
    ]}).json()['saved_event_dates'] == 1


def test_panel_deletion_retains_audit_and_blocks_reads_and_writes(app_data):
    client, store, base, panel, points, user_id = app_data
    accept(client, base, panel)
    with store() as session:
        original = Path(session.get(PointList, panel).path)
        original_content = original.read_bytes()
    assert client.delete(base + '/point-lists/' + panel).status_code == 200
    assert client.get(base).json()['point_lists'] == []
    assert client.get(base, params={'point_list_id': panel}).status_code == 404
    assert client.post(base + '/export-pdf', json={'point_list_id': panel}).status_code == 404
    assert client.post(base + '/accepted-points/save', json={'point_list_id': panel, 'rows': []}).status_code == 404
    assert client.patch(base + f'/point-lists/{panel}/points/{points[1]}/highlight', json={'highlighted': True}).status_code == 404
    assert client.post(base + '/event-dates/clear', json={'point_list_id': panel, 'confirmed': True}).status_code == 404
    assert 'error' in accept(client, base, panel).json()
    with store() as session:
        assert session.query(PointListDecision).count() == 2
        assert session.query(PointListEventDate).count() == 2
        assert session.query(SourceFile).count() == 1
        assert session.get(PointList, panel).deleted_by == user_id
        assert session.query(InspectionAuditEntry).filter_by(action='panel_deleted').one().decided_by == user_id
    assert original.read_bytes() == original_content


def test_admin_must_reset_and_missing_bootstrap_secret_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f"sqlite:///{tmp_path / 'bootstrap.db'}")
    from alarm_inspection.api.app import create_app
    monkeypatch.delenv('INSPECTIONS_BOOTSTRAP_ADMIN_PASSWORD')
    with pytest.raises(RuntimeError, match='INSPECTIONS_BOOTSTRAP_ADMIN_PASSWORD'):
        create_app()
    monkeypatch.setenv('INSPECTIONS_BOOTSTRAP_ADMIN_PASSWORD', PASSWORD)
    client = TestClient(create_app())
    assert client.post('/api/auth/login', json={'email': ADMIN, 'password': 'password'}).status_code == 401
    assert client.post('/api/auth/login', json={'email': ADMIN, 'password': PASSWORD}).status_code == 200
    assert client.get('/api/admin/users').status_code == 403
    assert client.get('/api/inspections').status_code == 403
    assert client.post('/api/auth/reset-password', json={'current_password': PASSWORD, 'new_password': 'ChangedPassword42!'}).status_code == 200
    assert client.get('/api/admin/users').status_code == 200
    monkeypatch.delenv('INSPECTIONS_BOOTSTRAP_ADMIN_PASSWORD')
    # Existing securely initialized installations can restart without the bootstrap secret.
    create_app()


def test_original_insecure_admin_is_rotated_and_old_sessions_revoked(app_data, monkeypatch):
    client, store, _, _, _, user_id = app_data
    from alarm_inspection.api.security import password_record, verify_password
    from alarm_inspection.api.app import create_app
    with store.begin() as session:
        admin = session.get(User, user_id)
        admin.password_hash = password_record('password')
        admin.force_password_reset = False
    monkeypatch.delenv('INSPECTIONS_BOOTSTRAP_ADMIN_PASSWORD')
    with pytest.raises(RuntimeError): create_app()
    monkeypatch.setenv('INSPECTIONS_BOOTSTRAP_ADMIN_PASSWORD', PASSWORD)
    create_app()
    with store() as session:
        admin = session.get(User, user_id)
        assert admin.force_password_reset and verify_password(PASSWORD, admin.password_hash)
        assert session.query(UserSession).count() == 0


def test_legacy_point_lists_migrate_without_losing_records(tmp_path, monkeypatch):
    database = tmp_path / 'legacy.db'
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{database}')
    engine = create_engine(f'sqlite:///{database}')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE point_lists (id VARCHAR(36) PRIMARY KEY, inspection_id VARCHAR(36), category VARCHAR(40), filename VARCHAR(255), path VARCHAR(1000), accepted_at DATETIME)'))
        connection.execute(text("INSERT INTO point_lists VALUES ('legacy', 'inspection', 'Fire', 'points.xlsx', '/original', '2026-10-01 10:00:00')"))
    store = open_store()
    with store() as session:
        panel = session.get(PointList, 'legacy')
        assert panel.filename == 'points.xlsx' and panel.deleted_at is None and panel.deleted_by is None


def test_table_save_and_clear_confirmation_in_browser(app_data):
    import os
    if os.getenv('INSPECTIONS_RUN_BROWSER_TESTS') != '1':
        pytest.skip('Opt-in browser regression')
    import socket
    import threading
    import time
    import uvicorn
    playwright = pytest.importorskip('playwright.sync_api')
    client, store, base, panel, points, _ = app_data
    accept(client, base, panel)
    inspection_id = base.rsplit('/', 1)[1]
    with store() as session:
        original_ids = {item.id for item in session.query(PointListEventDate)}
    sock = socket.socket(); sock.bind(('127.0.0.1', 0))
    server = uvicorn.Server(uvicorn.Config(client.app, log_level='error'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline: time.sleep(0.01)
    assert server.started
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            try:
                page = browser.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{sock.getsockname()[1]}')
                page.fill('#login-email', ADMIN); page.fill('#login-password', PASSWORD)
                page.locator('#login-form button').click()
                playwright.expect(page.locator('#home-screen')).to_be_visible()
                page.select_option('#inspection-picker', inspection_id); page.click('#open-inspection')
                playwright.expect(page.locator('.device-type-cell')).to_have_count(2)
                page.click('#edit-table')
                page.locator('.device-type-cell input').first.fill('Edited in browser')
                with page.expect_response(lambda r: r.url.endswith('/accepted-points/save')) as saved:
                    page.click('#save-table')
                assert saved.value.ok
                assert saved.value.request.post_data_json['rows'] == [{'id': points[1], 'text': 'Edited in browser'}]
                playwright.expect(page.locator('#inspection-message')).to_contain_text('Accepted Points saved')
                with store() as session:
                    assert {item.id for item in session.query(PointListEventDate)} == original_ids
                # Cancel must retain every accepted result.
                page.once('dialog', lambda dialog: dialog.dismiss())
                page.click('#inspection-menu-button'); page.click('#inspection-menu-option-clear-dates')
                with store() as session:
                    assert session.query(PointListEventDate).count() == 2
                page.once('dialog', lambda dialog: dialog.accept())
                page.click('#inspection-menu-button')
                with page.expect_response(lambda r: r.url.endswith('/event-dates/clear')) as cleared:
                    page.click('#inspection-menu-option-clear-dates')
                assert cleared.value.ok and cleared.value.request.post_data_json['confirmed'] is True
                playwright.expect(page.locator('#inspection-message')).to_contain_text('Cleared 2 saved dates')
                page.click('#inspection-menu-button')
                with page.expect_response(lambda r: r.url.endswith('/export-pdf')) as exported:
                    page.click('#inspection-menu-option-export-pdf')
                assert exported.value.status == 400
                playwright.expect(page.locator('#inspection-message')).to_contain_text('accepted test timestamp required')
                with store() as session:
                    assert session.query(InspectionAuditEntry).filter_by(action='event_results_cleared').count() == 1
                # Retiring a panel elsewhere must keep this inspection open and hide its rows.
                client.delete(base + '/point-lists/' + panel)
                playwright.expect(page.locator('#accepted-points-body')).to_contain_text('No accepted points', timeout=12000)
                playwright.expect(page.locator('#inspection-screen')).to_be_visible()
                playwright.expect(page.locator('#inspection-message')).to_contain_text('Points List was deleted')
                assert errors == []
            finally:
                browser.close()
    finally:
        server.should_exit = True; thread.join(timeout=5); sock.close()
