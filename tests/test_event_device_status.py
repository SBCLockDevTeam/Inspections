import io
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook

from alarm_inspection.storage import PointList, PointListDecision, PointListEventDate, PointListPendingEventDate, SourceFile, open_store


def workbook(rows):
    book = Workbook(); sheet = book.active
    for row in rows: sheet.append(row)
    data = io.BytesIO(); book.save(data)
    return data.getvalue()


def test_event_statuses_are_cumulative_shared_and_require_acceptance(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f"sqlite:///{tmp_path / 'events.db'}")
    from alarm_inspection.api.app import create_app
    client = TestClient(create_app())
    client.post('/api/auth/login', json={'email': 'john.porter@securitybuildingcontrols.com', 'password': 'TestBootstrapPassword42!'})
    client.post("/api/auth/reset-password", json={"current_password": "TestBootstrapPassword42!", "new_password": "TestBootstrapPassword42!"})
    inspection_id = client.post('/api/inspections/blank', json=dict(store_number='EVENTS', address='Test', city='Norfolk', state='VA', start_date='2026-10-01', completion_date='2026-10-02')).json()['id']
    store = open_store(); list_id, other_list_id = str(uuid4()), str(uuid4())
    point_ids = {address: str(uuid4()) for address in range(1, 6)}
    with store.begin() as session:
        for ident in (list_id, other_list_id):
            session.add(PointList(id=ident, inspection_id=inspection_id, category='Fire', filename='test.xlsx', path='test.xlsx', accepted_at=datetime.now(timezone.utc)))
        for address, ident in point_ids.items():
            session.add(PointListDecision(id=ident, inspection_id=inspection_id, point_list_id=list_id if address < 5 else other_list_id, address=address, text=f'Device {address}', accepted=True, deleted=False, device_highlighted=address != 3))
        session.add(PointListEventDate(id=str(uuid4()), inspection_id=inspection_id, point_list_id=list_id, point_address=4, event_timestamp=datetime(2026,10,1,9), source_filename='previous.xlsx'))
    def upload(rows):
        return client.post(f'/api/inspections/{inspection_id}/event-history', data={'point_list_id': list_id}, files={'event_file': ('history.xlsx', workbook([['Date', 'Zone', 'State'], *rows]), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}).json()
    def points():
        return {item['address']: item for item in client.get(f'/api/inspections/{inspection_id}?point_list_id={list_id}').json()['accepted_points']}
    result = upload([[datetime(2026,10,1,10), 1, 'A'], [datetime(2026,10,1,10), 99, 'T']])
    assert [item['point'] for item in result['pending_matches']] == [1]
    data = points()
    assert data[1]['pending_event_date'] and not data[1]['event_date'] and not data[1]['device_event_missing']
    assert data[2]['device_event_missing'] and data[2]['device_highlighted']
    assert not data[3]['device_event_missing'] and not data[3]['device_highlighted']
    assert data[4]['event_date'] and not data[4]['device_event_missing']
    with store() as session:
        assert session.query(PointListEventDate).count() == 1
        assert not session.get(PointListDecision, point_ids[5]).device_event_missing
    failed = client.post(f'/api/inspections/{inspection_id}/event-history', data={'point_list_id': list_id}, files={'event_file': ('history.xlsx', workbook([['Wrong header'], ['Bad data']]), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}).json()
    assert 'error' in failed and points()[2]['device_event_missing']
    # Another upload resolves yellow, retaining earlier unaccepted evidence.
    result = upload([[datetime(2026,10,1,11), 2, 'T'], [datetime(2026,10,1,12), 1, 'A']])
    assert [item['point'] for item in result['pending_matches']] == [1, 2]
    data = points(); assert not data[2]['device_event_missing'] and data[2]['pending_event_date']
    first_pending = data[1]['pending_event_date']
    result = upload([[datetime(2026,10,1,8), 1, 'T']])
    assert points()[1]['pending_event_date'] != first_pending
    assert not points()[2]['device_event_missing']
    with store() as session:
        sources = session.query(SourceFile).all()
        assert len({item.path for item in sources}) == 3
        assert all(__import__('pathlib').Path(item.path).exists() for item in sources)
        assert session.query(PointListEventDate).count() == 1
    # Only an explicit acceptance promotes evidence to an accepted mapping.
    match = next(item for item in result['pending_matches'] if item['point'] == 1)
    saved = client.post(f'/api/inspections/{inspection_id}/event-dates/save', json={'point_list_id': list_id, 'matches': [match]}).json()
    assert saved['saved'] == 1
    data = points(); assert data[1]['event_date'] and not data[1]['pending_event_date']
    accepted = data[1]['event_date']
    upload([[datetime(2026,10,1,7), 1, 'A']])
    assert points()[1]['event_date'] == accepted
    with store() as session:
        assert session.query(PointListPendingEventDate).count() == 1
        assert all(point.accepted and not point.deleted for point in session.query(PointListDecision))


def test_event_upload_review_reject_keep_and_clear_preserve_audit(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from alarm_inspection.storage import InspectionAuditEntry
    monkeypatch.setenv('DATABASE_URL', f"sqlite:///{tmp_path / 'review.db'}")
    from alarm_inspection.api.app import create_app
    client = TestClient(create_app())
    credentials = {'email': 'john.porter@securitybuildingcontrols.com', 'password': 'TestBootstrapPassword42!'}
    assert client.post('/api/auth/login', json=credentials).status_code == 200
    client.post('/api/auth/reset-password', json={'current_password': credentials['password'], 'new_password': credentials['password']})
    inspection = client.post('/api/inspections/blank', json=dict(store_number='REVIEW', address='Test',
        city='Norfolk', state='VA', start_date='2026-10-01', completion_date='2026-10-02')).json()['id']
    store = open_store()
    panel, other = str(uuid4()), str(uuid4())
    with store.begin() as session:
        for ident in (panel, other):
            session.add(PointList(id=ident, inspection_id=inspection, category='Fire', filename='test.xlsx',
                path='test.xlsx', accepted_at=datetime.now(timezone.utc)))
            session.add(PointListDecision(id=str(uuid4()), inspection_id=inspection, point_list_id=ident,
                address=1, text='Smoke', accepted=True, deleted=False))
            session.add(PointListEventDate(id=str(uuid4()), inspection_id=inspection, point_list_id=ident,
                point_address=1, event_timestamp=datetime(2026,10,1,9), source_filename='old.xlsx'))
        session.add(PointListDecision(id=str(uuid4()), inspection_id=inspection, point_list_id=panel,
            address=2, text='Pull', accepted=True, deleted=False))
        session.add(PointListPendingEventDate(inspection_id=inspection, point_list_id=panel,
            point_address=2, event_timestamp=datetime(2026,10,1,10), source_filename='pending.xlsx'))
    base = f'/api/inspections/{inspection}'
    def upload():
        response = client.post(base+'/event-history', data={'point_list_id': panel, 'review_required': 'true'},
            files={'event_file': ('new.xlsx', workbook([['Date','Zone','State'], [datetime(2026,10,2,11),1,'A'],
                [datetime(2026,10,2,12),2,'T']]))})
        assert response.status_code == 200
        return response.json()
    def review(candidate, action, **extra):
        return client.post(base+'/event-history/'+candidate['upload_id']+'/review',
            json={'point_list_id': panel, 'action': action, **extra})
    def times():
        with store() as session:
            return ([r.event_timestamp for r in session.query(PointListEventDate).order_by(PointListEventDate.point_list_id)],
                    [r.event_timestamp for r in session.query(PointListPendingEventDate)])
    before = times()
    candidate = upload()
    assert candidate['accepted_times'] == 1 and candidate['pending_times'] == 1
    assert times() == before  # Staging has no side effects on accepted or pending evidence.
    assert review(candidate, 'reject').json()['status'] == 'rejected'
    assert times() == before
    assert review(candidate, 'keep').status_code == 409
    candidate = upload()
    wrong = client.post(base+'/event-history/'+candidate['upload_id']+'/review', json={'point_list_id': other,'action':'reject'})
    assert wrong.status_code == 409
    assert review(candidate, 'keep').status_code == 200
    assert times() == before  # Later upload cannot replace prior accepted/earlier pending times.
    candidate = upload()
    assert review(candidate, 'clear').status_code == 400
    assert times() == before
    assert review(candidate, 'clear', confirmed=True).status_code == 200
    with store() as session:
        accepted = session.query(PointListEventDate).all()
        assert len(accepted) == 1 and accepted[0].point_list_id == other
        pending = session.query(PointListPendingEventDate).order_by(PointListPendingEventDate.point_address).all()
        assert [r.event_timestamp for r in pending] == [datetime(2026,10,2,11),datetime(2026,10,2,12)]
        assert all(Path(r.path).exists() for r in session.query(SourceFile))
        audit = session.query(InspectionAuditEntry).all()
        assert any(r.action == 'event_upload_rejected' for r in audit)
        cleared = next(json.loads(r.details_json) for r in audit if r.action == 'event_results_cleared')
        assert {r['state'] for r in cleared['previous']} == {'accepted','pending'}
    assert review(candidate, 'clear', confirmed=True).status_code == 409
