"""Admin lifecycle with actual bounded PDF processing and immutable versions."""
from io import BytesIO
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pypdf import PdfReader
from test_pdf_integration_storage import database
from pdf_storage_fixtures import template_bytes
from alarm_inspection.api.routers import admin_integrations
from alarm_inspection.integrations.pdf_models import PdfIntegrationVersion, PdfIntegration
from alarm_inspection.storage import User


@pytest.fixture
def admin_api(database,monkeypatch):
    store,files,inspection,_=database
    monkeypatch.setattr(admin_integrations,'UPLOAD_ROOT',files.root)
    app=FastAPI()
    @app.middleware('http')
    async def auth(request:Request,call_next):
        with store() as session: request.state.current_user=session.get(User,request.headers.get('x-actor','admin'))
        return await call_next(request)
    app.include_router(admin_integrations.create_router(store))
    return TestClient(app),store,files,inspection


def uploaded(client):
    response=client.post('/api/admin/integrations/compliance/templates',files={'file':('synthetic.pdf',template_bytes(),'application/pdf')})
    assert response.status_code==200,response.text
    return response.json()


def configured(client):
    draft=uploaded(client); config=draft['config']
    config.update(applicability='no_panel',applicability_reason='Reviewed synthetic policy',signature_policy='later_signing',supplemental_policy='not_applicable')
    config['mappings']=[{'target_id':t['id'],'disposition':'sign_later' if t['kind']=='signature' else 'blank','reason':'Reviewed deliberate blank'} for t in config['inventory']['targets']]
    response=client.put('/api/admin/integrations/versions/'+draft['id'],json={'config':config,'expected_revision':1})
    assert response.status_code==200,response.text
    return response.json()


def test_admin_intake_content_and_direct_authorization(admin_api):
    client,store,files,inspection=admin_api
    for method,path in [('get',''),('post','/compliance/templates'),('post','/versions/x/copy'),('put','/versions/x'),('post','/versions/x/test'),('post','/versions/x/publish'),('post','/compliance/state'),('get','/versions/x/pages/1'),('get','/tests/x')]:
        kwargs={'headers':{'x-actor':'tech'}}
        if method in {'put','post'}: kwargs['json']={}
        if path.endswith('templates'): kwargs.pop('json');kwargs['files']={'file':('synthetic.pdf',template_bytes())}
        assert getattr(client,method)('/api/admin/integrations'+path,**kwargs).status_code==403
    assert client.post('/api/admin/integrations/compliance/templates',files={'file':('bad.pdf',b'not pdf')}).status_code==400
    assert client.post('/api/admin/integrations/nfpa72/templates',files={'file':('short.pdf',template_bytes())}).status_code==400
    draft=uploaded(client)
    assert draft['config']['inventory']['selected_pages']==[1]
    page=client.get(f"/api/admin/integrations/versions/{draft['id']}/pages/1")
    assert page.status_code==200 and page.content.startswith(b'\x89PNG')
    assert client.get(f"/api/admin/integrations/versions/{draft['id']}/pages/2").status_code==400


def test_test_publish_activate_disable_copy_and_conflict(admin_api):
    client,store,files,inspection=admin_api
    draft=configured(client); path='/api/admin/integrations/versions/'+draft['id']
    assert client.put(path,json={'config':draft['config'],'expected_revision':1}).status_code==409
    test=client.post(path+'/test',json={'inspection_id':inspection,'expected_revision':2,'panel_ids':[]})
    assert test.status_code==200,test.text
    test=test.json()
    pdf=client.get('/api/admin/integrations/tests/'+test['test_artifact_id'])
    reader=PdfReader(BytesIO(pdf.content))
    assert len(reader.pages)==test['scenario_count'] and all('NOT AN INSPECTION REPORT' in p.extract_text() for p in reader.pages)
    assert all('/Annots' not in p for p in reader.pages)
    publish={'inspection_id':inspection,'expected_revision':2,'integration_revision':1,'test_artifact_id':test['test_artifact_id'],
             'verified_target_ids':test['target_ids'],'confirmed':True,'change_summary':'Reviewed every diagnostic page'}
    assert client.post(path+'/publish',json={**publish,'verified_target_ids':[]}).status_code==400
    response=client.post(path+'/publish',json=publish)
    assert response.status_code==200,response.text
    with store() as session:
        assert session.get(PdfIntegrationVersion,draft['id']).status=='published'
        assert session.get(PdfIntegration,'compliance').active_version_id==draft['id']
    assert client.put(path,json={'config':draft['config'],'expected_revision':3}).status_code==409
    assert client.post('/api/admin/integrations/compliance/state',json={'expected_revision':2,'enabled':True}).status_code==200
    assert client.post('/api/admin/integrations/compliance/state',json={'expected_revision':2,'enabled':False}).status_code==409
    assert client.post('/api/admin/integrations/compliance/state',json={'expected_revision':3,'enabled':False}).status_code==200
    copied=client.post(path+'/copy').json()
    assert copied['id']!=draft['id'] and copied['status']=='draft' and copied['verification']=={}


def test_incomplete_drafts_and_old_test_evidence_fail_closed(admin_api):
    client,store,files,inspection=admin_api
    draft=uploaded(client);path='/api/admin/integrations/versions/'+draft['id']
    assert client.post(path+'/test',json={'inspection_id':inspection,'expected_revision':1}).status_code==400
    draft=configured(client);path='/api/admin/integrations/versions/'+draft['id']
    test=client.post(path+'/test',json={'inspection_id':inspection,'expected_revision':2}).json()
    config=draft['config'];config['mappings'][0]['reason']='Changed reviewed policy'
    assert client.put(path,json={'config':config,'expected_revision':2}).status_code==200
    response=client.post(path+'/publish',json={'inspection_id':inspection,'expected_revision':3,'integration_revision':1,
        'test_artifact_id':test['test_artifact_id'],'verified_target_ids':test['target_ids'],'confirmed':True,'change_summary':'Changed'})
    assert response.status_code==400,response.text


def test_semantic_types_and_test_invalidation_on_source_definition_change(admin_api):
    from alarm_inspection.storage import InspectionTask
    client,store,files,inspection=admin_api
    draft=configured(client);path='/api/admin/integrations/versions/'+draft['id'];config=draft['config']
    text_target=next(t for t in config['inventory']['targets'] if t['kind']=='text')
    config['mappings']=[dict(m,disposition='source',source={'kind':'inspection','field':'start_date'},transforms=[{'kind':'time','format':'%H:%M','timezone':'UTC'}]) if m['target_id']==text_target['id'] else m for m in config['mappings']]
    assert client.put(path,json={'config':config,'expected_revision':2}).status_code==200
    failed=client.post(path+'/test',json={'inspection_id':inspection,'expected_revision':3})
    assert failed.status_code==400 and 'time' in failed.text.lower()
    config['mappings']=[dict(m,transforms=[]) for m in config['mappings']]
    assert client.put(path,json={'config':config,'expected_revision':3}).status_code==200
    test=client.post(path+'/test',json={'inspection_id':inspection,'expected_revision':4})
    assert test.status_code==200,test.text
    test=test.json()
    with store.begin() as session: session.get(InspectionTask,'task').input_type='textbox'
    response=client.post(path+'/publish',json={'inspection_id':inspection,'expected_revision':4,'integration_revision':1,
        'test_artifact_id':test['test_artifact_id'],'verified_target_ids':test['target_ids'],'confirmed':True,'change_summary':'Reviewed'})
    assert response.status_code==400 and 'retest' in response.text.lower()
