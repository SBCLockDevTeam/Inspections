"""Form isolation, legacy retention, and administrator-owned field help."""
from datetime import datetime, timezone
from uuid import uuid4

from test_inspection_tasks import task_app, make_inspection, add_task
from alarm_inspection.storage import InspectionChecklistDecision, User
from alarm_inspection.api.security import password_record


def test_named_forms_keep_answers_and_type_mapping(task_app):
    client, store = task_app
    ident = make_inspection(client)
    task = add_task(client, 'Panel model', section='nfpa72', input_type='textbox')
    shared = add_task(client, 'Shared compliance', input_type='textbox')
    base = f'/api/inspections/{ident}'
    assert client.patch(f'{base}/checklist/{task["id"]}', json={'value':'Original'}).status_code == 200
    assert client.post(base+'/nfpa-forms', json={'name':'Other','category':'Unknown'}).status_code == 422
    form = client.post(base+'/nfpa-forms', json={'name':'Fuel station', 'category':'Gas Station'}).json()
    assert form['category'] == 'Gas Station'
    assert len(client.get(base+'/nfpa-forms').json()['forms']) == 2
    suffix = '?nfpa_form_id='+form['id']
    rows = client.get(base+'/checklist'+suffix).json()['tasks']
    assert next(r for r in rows if r['id']==task['id'])['value'] == ''
    assert client.patch(f'{base}/checklist/{task["id"]}'+suffix, json={'value':'Second'}).status_code == 200
    assert client.patch(f'{base}/checklist/{shared["id"]}'+suffix, json={'value':'Shared'}).status_code == 200
    rows = client.get(base+'/checklist').json()['tasks']
    assert {r['text']:r['value'] for r in rows} == {'Panel model':'Original','Shared compliance':'Shared'}
    changed = client.put(base+'/nfpa-forms/original', json={'name':'Main fire panel','category':'Fire'})
    assert changed.status_code == 200
    assert client.get(base+'/nfpa-forms').json()['forms'][0]['category']=='Fire'
    other = make_inspection(client, 'OTHER')
    assert client.get(f'/api/inspections/{other}/checklist'+suffix).status_code == 404
    assert client.get(f'/api/inspections/{other}/nfpa-forms/{form["id"]}/form-integrations').status_code == 400
    with store() as session:
        assert session.query(InspectionChecklistDecision).count() == 3


def test_help_authorization_media_and_conflicts(task_app, tmp_path, monkeypatch):
    client, store = task_app
    fields = client.get('/api/admin/help').json()['fields']
    assert {f['section'] for f in fields} >= {'store_data','points'}
    field = 'builtin:store_number'
    url = '/api/admin/help/'+field
    content = {'enabled':True,'body':'Use the store sign. <script>never execute</script>','media':[],'revision':0}
    saved = client.put(url,json=content)
    assert saved.status_code == 200
    assert client.put(url,json=content).status_code == 409
    assert client.post(url+'/media',files={'file':('bad.svg',b'<svg></svg>','image/svg+xml')}).status_code == 422
    # A tiny PNG fixture with real bytes.
    import base64
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jGvQAAAAASUVORK5CYII=')
    media = client.post(url+'/media',files={'file':('example.png',png,'image/png')}).json()
    content.update(revision=1,media=[media['id']])
    assert client.put(url,json=content).status_code == 200
    assert client.put('/api/admin/help/builtin:city',json={**content,'revision':0}).status_code == 422
    user_id = str(uuid4())
    with store.begin() as session:
        session.add(User(id=user_id,email='help-tech@example.invalid',password_hash=password_record('TestPassword'),is_admin=False,force_password_reset=False,is_active=True,created_at=datetime.now(timezone.utc)))
    client.post('/api/auth/login',json={'email':'help-tech@example.invalid','password':'TestPassword'})
    assert client.get('/api/admin/help').status_code == 403
    assert client.put(url,json=content).status_code == 403
    assert client.get('/api/help').json()[field]['body']==content['body']
    assert client.get('/api/help/media/'+media['id']).content==png
    client.post('/api/auth/logout')
    assert client.get('/api/help/media/'+media['id']).status_code==401


def test_embedded_nfpa_drafts_do_not_overwrite_original(task_app, tmp_path, monkeypatch):
    from pdf_integration_fixtures import synthetic_form
    client, store = task_app
    template = tmp_path / 'template.pdf'
    template.write_bytes(synthetic_form())
    monkeypatch.setenv('NFPA_TEMPLATE_PATH', str(template))
    ident = make_inspection(client)
    base = f'/api/inspections/{ident}'
    form = client.post(base+'/nfpa-forms',json={'name':'Second panel','category':'Fire'}).json()
    path = base+'/pdf-templates/nfpa72'
    assert client.put(path,json={'fields':{'duplicate':'Original'}}).status_code == 200
    assert client.put(path+'?nfpa_form_id='+form['id'],json={'fields':{'duplicate':'Second'}}).status_code == 200
    assert client.get(path).json()['fields']['duplicate']=='Original'
    assert client.get(path+'?nfpa_form_id='+form['id']).json()['fields']['duplicate']=='Second'


def test_existing_checklist_column_migration_preserves_answers(task_app):
    from sqlalchemy import text
    from alarm_inspection.storage import open_store
    client, store = task_app
    ident = make_inspection(client)
    task = add_task(client, 'Legacy model', section='nfpa72', input_type='textbox')
    assert client.patch(f'/api/inspections/{ident}/checklist/{task["id"]}',json={'value':'Retained'}).status_code==200
    with store.kw['bind'].begin() as connection:
        connection.execute(text('ALTER TABLE inspection_checklist_decisions DROP COLUMN nfpa_form_id'))
    migrated = open_store()
    with migrated() as session:
        decision=session.query(InspectionChecklistDecision).one()
        assert decision.value=='Retained' and decision.nfpa_form_id==''
