from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alarm_inspection.storage import PointList, PointListDecision, open_store


def test_highlights_are_persisted_and_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f"sqlite:///{tmp_path / 'highlight.db'}")
    from alarm_inspection.api.app import create_app
    client = TestClient(create_app())
    client.post('/api/auth/login', json={'email': 'john.porter@securitybuildingcontrols.com', 'password': 'password'})
    def make(number):
        return client.post('/api/inspections/blank', json=dict(store_number=number, address='Test', city='Norfolk', state='VA', start_date='2026-10-01', completion_date='2026-10-02')).json()['id']
    one, two = make('1'), make('2')
    store = open_store()
    list_id, point_id, other_id = (str(uuid4()) for _ in range(3))
    with store.begin() as session:
        session.add(PointList(id=list_id, inspection_id=one, category='Fire', filename='test.xlsx', path='test.xlsx', accepted_at=datetime.now(timezone.utc)))
        for ident, accepted in ((point_id, True), (other_id, False)):
            session.add(PointListDecision(id=ident, inspection_id=one, point_list_id=list_id, address=1, text='Smoke', accepted=accepted, deleted=False))
    path = f'/api/inspections/{one}/point-lists/{list_id}/points/{point_id}/highlight'
    assert client.get(f'/api/inspections/{one}').json()['accepted_points'][0]['device_highlighted'] is False
    assert client.patch(path, json={'highlighted': 'true'}).status_code == 422
    assert client.patch(path.replace(one, two), json={'highlighted': True}).status_code == 404
    assert client.patch(path.replace(point_id, other_id), json={'highlighted': True}).status_code == 404
    for value in (True, False, True):
        assert client.patch(path, json={'highlighted': value}).status_code == 200
        assert client.get(f'/api/inspections/{one}').json()['accepted_points'][0]['device_highlighted'] is value
    with store() as session:
        point = session.get(PointListDecision, point_id)
        assert point.accepted and not point.deleted and point.text == 'Smoke'
    anonymous = TestClient(client.app)
    assert anonymous.patch(path, json={'highlighted': False}).status_code == 401
    client.delete(f'/api/inspections/{one}')
    assert client.patch(path, json={'highlighted': False}).status_code == 404


def test_existing_decisions_get_unhighlighted_default(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    monkeypatch.setenv('DATABASE_URL', url)
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE point_list_decisions (id VARCHAR(36) PRIMARY KEY, inspection_id VARCHAR(36), point_list_id VARCHAR(36), address INTEGER, text VARCHAR(500), location VARCHAR(500), accepted BOOLEAN, deleted BOOLEAN, reason VARCHAR(200))'))
        connection.execute(text("INSERT INTO point_list_decisions VALUES ('old','inspection','list',1,'Smoke','Lobby',1,0,'accepted')"))
    store = open_store()
    with store() as session:
        point = session.get(PointListDecision, 'old')
        assert point.device_event_missing is False
        assert point.device_highlighted is False and point.accepted and point.location == 'Lobby'
