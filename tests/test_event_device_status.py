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
