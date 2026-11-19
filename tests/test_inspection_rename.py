"""Only admins can persist custom inspection names; other saved facts are retained."""
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from test_panel_types import panel_app, inspection_payload
from alarm_inspection.storage import Inspection, InspectionAuditEntry, User, open_store
from alarm_inspection.api.security import password_record


def test_admin_rename_persists_through_details_and_restart(panel_app):
    client, store = panel_app
    created = client.post('/api/inspections/blank', json=inspection_payload()).json()
    ident, original = created['id'], created['name']
    url = f'/api/inspections/{ident}'
    result = client.patch(url+'/name', json={'name': '  Special   Inspection  ', 'expected_name': original})
    assert result.status_code == 200
    assert result.json()['name'] == 'Special Inspection'
    assert client.get(url).json()['name'] == 'Special Inspection'
    assert client.get('/api/inspections').json()[0]['name'] == 'Special Inspection'
    assert client.patch(url, json={'city': 'Richmond'}).json()['name'] == 'Special Inspection'
    assert client.patch(url+'/name', json={'name': 'Stale', 'expected_name': original}).status_code == 409
    with open_store()() as session:
        row = session.get(Inspection, ident)
        assert row.name == 'Special Inspection' and row.store_number == '0042'
        audit = session.query(InspectionAuditEntry).filter_by(action='inspection_renamed').one()
        assert json.loads(audit.details_json) == {'before': original, 'after': 'Special Inspection'}
        assert audit.decided_by and audit.decided_at
    # Any administrator, not just the bootstrap administrator, may rename.
    with store.begin() as session:
        session.add(User(id=str(uuid4()), email='other@example.invalid', is_admin=True,
                         password_hash=password_record('TestPassword'), force_password_reset=False,
                         is_active=True, created_at=datetime.now(timezone.utc)))
    client.post('/api/auth/login', json={'email': 'other@example.invalid', 'password': 'TestPassword'})
    assert client.patch(url+'/name', json={'name': 'Another name', 'expected_name': 'Special Inspection'}).status_code == 200
    with store.begin() as session:
        session.query(User).filter_by(email='other@example.invalid').one().is_admin = False
    assert client.patch(url+'/name', json={'name': 'Denied', 'expected_name': 'Another name'}).status_code == 403
    # Ordinary detail updates cannot bypass the admin-only endpoint.
    client.patch(url, json={'name': 'Denied', 'custom_name': 'Denied'})
    assert client.get(url).json()['name'] == 'Another name'
    client.post('/api/auth/logout')
    assert client.patch(url+'/name', json={'name': 'Denied', 'expected_name': 'Another name'}).status_code == 401


@pytest.mark.parametrize('name', ['', '   ', 'x'*201, None, 42])
def test_invalid_rename_is_rejected(panel_app, name):
    client, store = panel_app
    created = client.post('/api/inspections/blank', json=inspection_payload()).json()
    url = f"/api/inspections/{created['id']}"
    assert client.patch(url+'/name', json={'name': name, 'expected_name': created['name']}).status_code == 422
    assert client.get(url).json()['name'] == created['name']


def test_missing_and_deleted_inspections_cannot_be_renamed(panel_app):
    client, store = panel_app
    created = client.post('/api/inspections/blank', json=inspection_payload()).json()
    with store.begin() as session:
        session.get(Inspection, created['id']).status = 'deleted'
    for ident in (created['id'], 'missing'):
        assert client.patch(f'/api/inspections/{ident}/name', json={'name': 'New', 'expected_name': created['name']}).status_code == 404
