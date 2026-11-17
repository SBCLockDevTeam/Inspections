"""Explicit deletion retains evidence and cannot cross inspection/panel boundaries."""
import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from test_review_fixes import app_data, accept
from alarm_inspection.storage import InspectionAuditEntry, PointListDecision, PointListEventDate, SourceFile


def test_delete_requires_confirmation_and_retains_audit(app_data):
    client, store, base, panel, points, user = app_data
    accept(client, base, panel)
    path = f'{base}/point-lists/{panel}/points/{points[1]}'
    assert TestClient(client.app).request('DELETE', path, json={'confirmed': True}).status_code == 401
    for payload, code in [({}, 422), ({'confirmed': 'true'}, 422), ({'confirmed': False}, 400)]:
        assert client.request('DELETE', path, json=payload).status_code == code
    assert client.request('DELETE', path.replace(panel, str(uuid4())), json={'confirmed': True}).status_code == 404
    assert client.request('DELETE', path.replace(base, '/api/inspections/'+str(uuid4())), json={'confirmed': True}).status_code == 404
    assert client.request('DELETE', path, json={'confirmed': True}).status_code == 200
    assert [p['id'] for p in client.get(base).json()['accepted_points']] == [points[2]]
    # A stale save cannot resurrect a deleted row or overwrite its retained data.
    client.post(base+'/accepted-points/save', json={'point_list_id': panel, 'rows': [{'id': points[1], 'text': 'stale'}]})
    with store() as session:
        point = session.get(PointListDecision, points[1])
        assert point.deleted and point.accepted and point.text == 'Smoke'
        assert session.query(PointListEventDate).count() == 2
        assert all(Path(f.path).exists() for f in session.query(SourceFile).all())
        entry = session.query(InspectionAuditEntry).filter_by(action='point_deleted').one()
        assert entry.decided_by == user and entry.decided_at
        assert json.loads(entry.details_json)['point_id'] == points[1]
    assert client.request('DELETE', path, json={'confirmed': True}).status_code == 404
    # The surviving point still exports; deleting the last point blocks an empty report.
    assert client.post(base+'/export-pdf', json={'point_list_id': panel}).status_code == 200
    assert client.request('DELETE', path.replace(points[1], points[2]), json={'confirmed': True}).status_code == 200
    assert client.post(base+'/export-pdf', json={'point_list_id': panel}).status_code == 400
