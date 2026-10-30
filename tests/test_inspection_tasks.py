from datetime import datetime, timezone
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from alarm_inspection.storage import InspectionTask, InspectionChecklistDecision, User


@pytest.fixture
def task_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tasks.db'}")
    from alarm_inspection.api.app import create_app
    from alarm_inspection.storage import open_store
    client = TestClient(create_app())
    assert client.post("/api/auth/login", json={"email": "john.porter@securitybuildingcontrols.com", "password": "TestBootstrapPassword42!"}).status_code == 200
    client.post("/api/auth/reset-password", json={"current_password": "TestBootstrapPassword42!", "new_password": "TestBootstrapPassword42!"})
    return client, open_store()


def make_inspection(client, number="0042"):
    return client.post("/api/inspections/blank", json=dict(store_number=number, address="123 Test St", city="Norfolk", state="VA", start_date="2026-10-01", completion_date="2026-10-02")).json()["id"]


def add_task(client, text="Notify monitoring station", **extra):
    result = client.post("/api/admin/inspection-tasks", json={"text": text, **extra})
    assert result.status_code == 201
    return result.json()["task"]


def test_task_management_order_and_duplicates(task_app):
    client, store = task_app
    assert client.get("/api/admin/inspection-tasks").json() == {"tasks": []}
    task = add_task(client, "  Notify   monitoring station  ", position=4)
    assert task["text"] == "Notify monitoring station"
    second = add_task(client, "Restore system", position=2)
    assert [t["id"] for t in client.get("/api/admin/inspection-tasks").json()["tasks"]] == [second["id"], task["id"]]
    assert client.post("/api/admin/inspection-tasks", json={"text": "notify monitoring station"}).status_code == 409
    assert client.patch("/api/admin/inspection-tasks/" + second["id"], json={"text": task["text"]}).status_code == 409
    result = client.patch("/api/admin/inspection-tasks/" + task["id"], json={"text": "Notify central station", "position": 1, "active": False})
    assert result.status_code == 200
    with store() as session:
        row = session.get(InspectionTask, task["id"])
        assert row.text == "Notify central station" and row.position == 1 and not row.active
        assert session.get(InspectionTask, second["id"]).text == "Restore system"


@pytest.mark.parametrize("payload", [{"text": " "}, {"text": "x" * 201}, {"text": "Task", "position": 0}, {"text": "Task", "position": True}])
def test_invalid_tasks_are_not_created(task_app, payload):
    client, store = task_app
    assert client.post("/api/admin/inspection-tasks", json=payload).status_code == 422
    with store() as session:
        assert session.query(InspectionTask).count() == 0


def test_independent_checklists_preserve_decision_history(task_app):
    client, store = task_app
    one, two = make_inspection(client), make_inspection(client, "0043")
    assert client.get(f"/api/inspections/{one}/checklist").json()["tasks"] == []
    task = add_task(client)
    path = f"/api/inspections/{one}/checklist/{task['id']}"
    for value in (True, False, True):
        assert client.patch(path, json={"completed": value}).status_code == 200
    assert client.get(f"/api/inspections/{one}/checklist").json()["completed_count"] == 1
    assert client.get(f"/api/inspections/{two}/checklist").json()["completed_count"] == 0
    client.patch(f"/api/admin/inspection-tasks/{task['id']}", json={"text": "Notify central station", "active": False})
    assert client.get(f"/api/inspections/{one}/checklist").json()["tasks"] == []
    assert client.patch(path, json={"completed": False}).status_code == 404
    client.patch(f"/api/admin/inspection-tasks/{task['id']}", json={"active": True})
    reopened = client.get(f"/api/inspections/{one}/checklist").json()
    assert reopened["tasks"][0]["completed"] and reopened["tasks"][0]["text"] == "Notify central station"
    add_task(client, "Restore system")
    checklist = client.get(f"/api/inspections/{one}/checklist").json()
    assert checklist["total_count"] == 2 and checklist["completed_count"] == 1
    with store() as session:
        decisions = session.query(InspectionChecklistDecision).order_by(InspectionChecklistDecision.decided_at).all()
        assert [row.completed for row in decisions] == [True, False, True]
        assert all(row.task_text == "Notify monitoring station" and row.decided_by for row in decisions)
    client.delete(f"/api/inspections/{one}")
    assert client.get(f"/api/inspections/{one}/checklist").status_code == 404
    with store() as session:
        assert session.query(InspectionChecklistDecision).count() == 3


def test_technician_can_check_tasks_but_not_manage_definitions(task_app):
    client, store = task_app
    from alarm_inspection.api.security import password_record
    task = add_task(client)
    inspection = make_inspection(client)
    user_id = str(uuid4())
    with store.begin() as session:
        session.add(User(id=user_id, email="task-tech@example.invalid", password_hash=password_record("TestPassword"), is_admin=False, force_password_reset=False, is_active=True, created_at=datetime.now(timezone.utc)))
    client.post("/api/auth/login", json={"email": "task-tech@example.invalid", "password": "TestPassword"})
    assert client.get("/api/admin/inspection-tasks").status_code == 403
    assert client.post("/api/admin/inspection-tasks", json={"text": "Denied"}).status_code == 403
    assert client.patch(f"/api/admin/inspection-tasks/{task['id']}", json={"active": False}).status_code == 403
    assert client.patch(f"/api/inspections/{inspection}/checklist/{task['id']}", json={"completed": True}).status_code == 200
    with store() as session:
        assert session.query(InspectionChecklistDecision).one().decided_by == user_id
    client.post("/api/auth/logout")
    assert client.get(f"/api/inspections/{inspection}/checklist").status_code == 401


def test_invalid_checklist_updates_create_no_decisions(task_app):
    client, store = task_app
    task = add_task(client)
    inspection = make_inspection(client)
    assert client.patch(f"/api/inspections/{inspection}/checklist/{task['id']}", json={"completed": "false"}).status_code == 422
    assert client.patch(f"/api/inspections/missing/checklist/{task['id']}", json={"completed": True}).status_code == 404
    assert client.patch(f"/api/inspections/{inspection}/checklist/missing", json={"completed": True}).status_code == 404
    assert client.patch(f"/api/admin/inspection-tasks/{task['id']}", json={"active": None}).status_code == 422
    with store() as session:
        assert session.query(InspectionChecklistDecision).count() == 0


@pytest.mark.parametrize('extra', [
    {'input_type': 'unknown'}, {'input_type': 'dropdown'},
    {'input_type': 'dropdown', 'options': [' ']},
    {'input_type': 'dropdown', 'options': ['Ready', 'ready']},
    {'input_type': 'dropdown', 'options': ['x' * 121]},
    {'input_type': 'dropdown', 'options': list(map(str, range(51)))},
    {'input_type': 'textbox', 'options': ['Invalid']},
    {'input_type': 'dropdown', 'options': [42]},
])
def test_invalid_checklist_types_and_choices(task_app, extra):
    client, store = task_app
    assert client.post('/api/admin/inspection-tasks', json={'text': 'Typed task', **extra}).status_code == 422
    with store() as session:
        assert session.query(InspectionTask).count() == 0


def test_typed_values_and_removed_choices_preserve_audit_history(task_app):
    import json
    client, store = task_app
    one, two = make_inspection(client), make_inspection(client, '0043')
    text = add_task(client, 'Panel serial number', input_type='textbox')
    dropdown = add_task(client, 'Panel condition', input_type='dropdown', options=['  Ready  ', 'Needs repair'])
    check = add_task(client, 'Restored system')
    assert dropdown['options'] == ['Ready', 'Needs repair']
    path = f'/api/inspections/{one}/checklist'
    assert client.patch(path+'/'+text['id'], json={'value': 'SN-00042'}).status_code == 200
    assert client.patch(path+'/'+dropdown['id'], json={'value': 'Ready'}).status_code == 200
    assert client.patch(path+'/'+check['id'], json={'completed': True}).status_code == 200
    assert client.get(path).json()['completed_count'] == 3
    assert client.get(f'/api/inspections/{two}/checklist').json()['completed_count'] == 0
    for payload in ({'value': 'Missing choice'}, {'completed': True}, {'value': 42}):
        assert client.patch(path+'/'+dropdown['id'], json=payload).status_code == 422
    assert client.patch(path+'/'+text['id'], json={'value': 'x'*2001}).status_code == 422
    assert client.patch(path+'/'+check['id'], json={'value': 'yes'}).status_code == 422
    # Removing an option retains the earlier selection and its original option snapshot.
    assert client.patch('/api/admin/inspection-tasks/'+dropdown['id'], json={'options': ['Needs repair', 'Not tested']}).status_code == 200
    rows = {row['id']: row for row in client.get(path).json()['tasks']}
    assert rows[dropdown['id']]['value'] == 'Ready' and rows[dropdown['id']]['removed_choice']
    with store() as session:
        saved = session.query(InspectionChecklistDecision).filter_by(task_id=dropdown['id']).one()
        assert saved.value == 'Ready' and json.loads(saved.options_json) == ['Ready', 'Needs repair']
        assert saved.input_type == 'dropdown' and saved.decided_by
    assert client.patch(path+'/'+dropdown['id'], json={'value': 'Needs repair'}).status_code == 200
    assert client.patch(path+'/'+text['id'], json={'value': ''}).status_code == 200
    assert client.get(path).json()['completed_count'] == 2
    # Changing the task type keeps old answers in history without reinterpreting them.
    assert client.patch('/api/admin/inspection-tasks/'+check['id'], json={'input_type': 'textbox'}).status_code == 200
    row = next(row for row in client.get(path).json()['tasks'] if row['id'] == check['id'])
    assert row['previous_type'] == 'checkbox' and not row['completed'] and row['value'] == ''
    assert client.patch(path+'/'+check['id'], json={'completed': False}).status_code == 422
    assert client.patch(path+'/'+check['id'], json={'value': 'System restored'}).status_code == 200
    with store() as session:
        answers = session.query(InspectionChecklistDecision).filter_by(task_id=check['id']).order_by(InspectionChecklistDecision.decided_at).all()
        assert [item.input_type for item in answers] == ['checkbox', 'textbox']
        assert answers[0].completed and answers[1].value == 'System restored'


def test_legacy_checklist_migration_preserves_existing_answers(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text
    from alarm_inspection.storage import open_store
    url = f"sqlite:///{tmp_path / 'legacy-checklist.db'}"
    monkeypatch.setenv('DATABASE_URL', url)
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE inspection_tasks (id VARCHAR(36) PRIMARY KEY, text VARCHAR(200), text_key VARCHAR(600), position INTEGER, active BOOLEAN, created_at DATETIME)'))
        connection.execute(text("INSERT INTO inspection_tasks VALUES ('old-task','Old task','old task',1,1,'2026-10-01')"))
        connection.execute(text('CREATE TABLE inspection_checklist_decisions (id VARCHAR(36) PRIMARY KEY, inspection_id VARCHAR(36), task_id VARCHAR(36), task_text VARCHAR(200), completed BOOLEAN, decided_by VARCHAR(36), decided_at DATETIME)'))
        connection.execute(text("INSERT INTO inspection_checklist_decisions VALUES ('old-answer','inspection','old-task','Old task',1,'user','2026-10-01')"))
    store = open_store()
    with store() as session:
        task = session.get(InspectionTask, 'old-task'); answer = session.get(InspectionChecklistDecision, 'old-answer')
        assert task.input_type == 'checkbox' and task.options_json == '[]'
        assert answer.input_type == 'checkbox' and answer.completed and answer.decided_by == 'user'


def test_checkbox_answers_are_exclusive_audited_and_independent(task_app):
    import json
    client, store = task_app
    task = add_task(client)
    one, two = make_inspection(client), make_inspection(client, '0043')
    path = f'/api/inspections/{one}/checklist'
    for value in ('Yes', 'No', 'NA', ''):
        result = client.patch(path+'/'+task['id'], json={'value': value})
        assert result.status_code == 200
        assert result.json()['value'] == value
        rows = client.get(path).json()
        assert rows['tasks'][0]['value'] == value
        assert rows['completed_count'] == int(bool(value))
        assert client.get(f'/api/inspections/{two}/checklist').json()['tasks'][0]['value'] == ''
    for payload in ({'value': 'Yes,No'}, {'value': ['Yes', 'No']}, {'value': 'N/A'},
                    {'value': 'Yes', 'completed': True}, {}, {'value': None}):
        assert client.patch(path+'/'+task['id'], json=payload).status_code == 422
    with store() as session:
        decisions = session.query(InspectionChecklistDecision).filter_by(task_id=task['id']).order_by(InspectionChecklistDecision.decided_at).all()
        assert [d.value for d in decisions] == ['Yes', 'No', 'NA', '']
        assert [d.completed for d in decisions] == [True, True, True, False]
        assert all(json.loads(d.options_json) == ['Yes', 'No', 'NA'] and d.decided_by and d.decided_at for d in decisions)


def test_existing_checkbox_answers_use_new_format_without_rewriting_history(task_app):
    client, store = task_app
    one, two = make_inspection(client), make_inspection(client, '0043')
    task = add_task(client)
    with store.begin() as session:
        for inspection_id, completed in ((one, True), (two, False)):
            session.add(InspectionChecklistDecision(
                id=str(uuid4()), inspection_id=inspection_id, task_id=task['id'],
                task_text=task['text'], input_type='checkbox', completed=completed,
                value='', options_json='[]', decided_by='original-user',
                decided_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            ))
    for inspection_id, value in ((one, 'Yes'), (two, '')):
        for _ in range(2):
            row = client.get(f'/api/inspections/{inspection_id}/checklist').json()['tasks'][0]
            assert row['input_type'] == 'checkbox' and row['value'] == value
            assert row['completed'] == bool(value)
    with store() as session:
        decisions = session.query(InspectionChecklistDecision).all()
        assert len(decisions) == 2
        assert all(d.value == '' and d.options_json == '[]' and d.decided_by == 'original-user' for d in decisions)
    # Subsequent choices append a decision rather than replacing the legacy answer.
    assert client.patch(f'/api/inspections/{one}/checklist/{task["id"]}', json={'value': 'NA'}).status_code == 200
    with store() as session:
        assert session.query(InspectionChecklistDecision).count() == 3


def test_sections_move_fields_without_changing_answers(task_app):
    client,store=task_app;inspection=make_inspection(client)
    field=add_task(client,'NFPA panel notes',section='nfpa72',input_type='textbox')
    assert field['section']=='nfpa72'
    response=client.patch(f'/api/inspections/{inspection}/checklist/{field["id"]}',json={'value':'Existing panel notes'})
    assert response.status_code==200
    response=client.patch('/api/admin/inspection-tasks/'+field['id'],json={'section':'compliance'})
    assert response.status_code==200 and response.json()['task']['section']=='compliance'
    rows=client.get(f'/api/inspections/{inspection}/checklist').json()['tasks']
    assert next(row for row in rows if row['id']==field['id'])['value']=='Existing panel notes'
    with store() as session:
        decision=session.query(InspectionChecklistDecision).filter_by(task_id=field['id']).one()
        assert decision.value=='Existing panel notes'
    assert client.post('/api/admin/inspection-tasks',json={'text':'Invalid section','section':'points'}).status_code==422
    assert client.patch('/api/admin/inspection-tasks/'+field['id'],json={'section':None}).status_code==422


def test_legacy_section_migration_moves_only_panel_fields_once(tmp_path,monkeypatch):
    from sqlalchemy import create_engine,text
    from alarm_inspection.storage import open_store,InspectionTask
    url=f'sqlite:///{tmp_path / "legacy-section.db"}'
    engine=create_engine(url)
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE inspection_tasks (id VARCHAR(36) PRIMARY KEY, text VARCHAR(200), text_key VARCHAR(600) UNIQUE, input_type VARCHAR(20), options_json TEXT, position INTEGER, active BOOLEAN, created_at DATETIME)'))
        for ident,label in [('panel','Panel Model'),('firmware','Firmware version'),('other','Check doors')]:
            connection.execute(text("INSERT INTO inspection_tasks VALUES (:id,:label,:key,'textbox','[]',1,1,'2026-10-29 00:00:00')"),dict(id=ident,label=label,key=label.casefold()))
    engine.dispose();monkeypatch.setenv('DATABASE_URL',url)
    store=open_store()
    with store.begin() as session:
        assert session.get(InspectionTask,'panel').section=='nfpa72'
        assert session.get(InspectionTask,'firmware').section=='nfpa72'
        assert session.get(InspectionTask,'other').section=='compliance'
        session.get(InspectionTask,'panel').section='compliance'
    another=open_store()
    with another() as session:assert session.get(InspectionTask,'panel').section=='compliance'
    store.kw['bind'].dispose();another.kw['bind'].dispose()


def test_section_move_preserves_dropdown_definition_bytes(task_app):
    client,store=task_app
    field=add_task(client,'Panel Model choices',input_type='dropdown',options=['A','B'])
    with store.begin() as session:session.get(InspectionTask,field['id']).options_json='["A","B"]'
    response=client.patch('/api/admin/inspection-tasks/'+field['id'],json={'section':'nfpa72','input_type':'dropdown','options':['A','B']})
    assert response.status_code==200
    with store() as session:assert session.get(InspectionTask,field['id']).options_json=='["A","B"]'


def test_store_data_custom_field_uses_existing_value_history(task_app):
    client,store=task_app;inspection=make_inspection(client)
    task=add_task(client,'Store contact phone',section='store_data',input_type='textbox')
    assert task['section']=='store_data'
    response=client.patch(f'/api/inspections/{inspection}/checklist/{task["id"]}',json={'value':'555-0100'})
    assert response.status_code==200
    field=next(row for row in client.get(f'/api/inspections/{inspection}/checklist').json()['tasks'] if row['id']==task['id'])
    assert field['section']=='store_data' and field['value']=='555-0100'
    assert client.patch('/api/admin/inspection-tasks/'+task['id'],json={'section':'nfpa72'}).status_code==200
    with store() as session:
        assert session.query(InspectionChecklistDecision).filter_by(task_id=task['id']).one().value=='555-0100'


@pytest.mark.parametrize('kind,options,default', [
    ('checkbox', [], 'Yes'), ('checkbox', [], 'No'), ('checkbox', [], 'NA'), ('checkbox', [], ''),
    ('textbox', [], 'Default contact'), ('dropdown', ['Ready', 'Repair'], 'Ready'),
])
def test_typed_defaults_never_replace_explicit_answers(task_app, kind, options, default):
    client, store = task_app
    inspection = make_inspection(client)
    task = add_task(client, 'Default task', input_type=kind, options=options, default_value=default)
    path = f'/api/inspections/{inspection}/checklist'
    row = client.get(path).json()['tasks'][0]
    assert row['value'] == default and row['default_applied'] == bool(default)
    with store() as session:
        assert session.query(InspectionChecklistDecision).count() == 0
    # Explicitly clearing a value suppresses future defaults, including after a change.
    assert client.patch(path+'/'+task['id'], json={'value': ''}).status_code == 200
    replacement = 'No' if kind == 'checkbox' else 'Repair' if kind == 'dropdown' else 'New contact'
    assert client.patch('/api/admin/inspection-tasks/'+task['id'], json={'default_value': replacement}).status_code == 200
    row = client.get(path).json()['tasks'][0]
    assert row['value'] == '' and not row['default_applied']
    another = make_inspection(client, '0043')
    assert client.get(f'/api/inspections/{another}/checklist').json()['tasks'][0]['value'] == replacement
    with store() as session:
        assert session.query(InspectionChecklistDecision).count() == 1


@pytest.mark.parametrize('extra', [
    {'default_value': True}, {'default_value': 'checked'}, {'default_value': None},
    {'input_type': 'textbox', 'default_value': 'x'*2001},
    {'input_type': 'dropdown', 'options': ['Ready'], 'default_value': 'Repair'},
])
def test_invalid_defaults_rejected(task_app, extra):
    client, _ = task_app
    assert client.post('/api/admin/inspection-tasks', json={'text': 'Invalid default', **extra}).status_code == 422


def test_default_validation_on_edit_and_type_change(task_app):
    client, _ = task_app
    task = add_task(client, input_type='dropdown', options=['Ready', 'Repair'], default_value='Ready')
    path = '/api/admin/inspection-tasks/'+task['id']
    assert client.patch(path, json={'default_value': 'Invalid'}).status_code == 422
    assert client.get('/api/admin/inspection-tasks').json()['tasks'][0]['default_value'] == 'Ready'
    assert client.patch(path, json={'options': ['Repair']}).json()['task']['default_value'] == ''
    assert client.patch(path, json={'input_type': 'textbox', 'default_value': 'Contact'}).status_code == 200
    assert client.patch(path, json={'input_type': 'checkbox'}).json()['task']['default_value'] == ''
    assert client.patch(path, json={'default_value': None}).status_code == 422


def test_atomic_section_reorder_conflicts_and_history(task_app):
    client, store = task_app
    first = add_task(client, 'First', section='nfpa72')
    second = add_task(client, 'Second', section='nfpa72')
    other = add_task(client, 'Other', section='store_data')
    inspection = make_inspection(client)
    client.patch(f'/api/inspections/{inspection}/checklist/{first["id"]}', json={'value': 'Yes'})
    request = {'section': 'nfpa72', 'expected_order': [first['id'], second['id']], 'task_ids': [second['id'], first['id']]}
    assert client.put('/api/admin/inspection-tasks/order', json=request).status_code == 200
    assert client.put('/api/admin/inspection-tasks/order', json=request).status_code == 409
    for ids in ([first['id'], first['id']], [first['id']], [other['id'], first['id']]):
        assert client.put('/api/admin/inspection-tasks/order', json={**request, 'task_ids': ids}).status_code == 409
    third = add_task(client, 'Third', section='nfpa72')
    assert third['position'] == 3
    rows = client.get(f'/api/inspections/{inspection}/checklist').json()['tasks']
    assert [t['id'] for t in rows if t['section'] == 'nfpa72'] == [second['id'], first['id'], third['id']]
    with store() as session:
        assert session.get(InspectionTask, other['id']).position == other['position']
        assert session.query(InspectionChecklistDecision).one().value == 'Yes'


def test_default_column_migration_is_additive_and_repeatable(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text
    from alarm_inspection.storage import open_store
    url = f"sqlite:///{tmp_path / 'default-migration.db'}"
    monkeypatch.setenv('DATABASE_URL', url)
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE inspection_tasks (id VARCHAR(36) PRIMARY KEY, text VARCHAR(200), text_key VARCHAR(600), section VARCHAR(20), input_type VARCHAR(20), options_json TEXT, position INTEGER, active BOOLEAN, created_at DATETIME)'))
        connection.execute(text("INSERT INTO inspection_tasks VALUES ('original', 'Panel model', 'panel model', 'store_data', 'textbox', '[]', 8, 1, '2026-10-01 00:00:00')"))
    for _ in range(2):
        store = open_store()
        with store() as session:
            task = session.get(InspectionTask, 'original')
            assert task.default_value == '' and task.section == 'store_data' and task.position == 8
