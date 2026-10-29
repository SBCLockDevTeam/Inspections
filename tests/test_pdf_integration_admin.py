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


def test_failed_intake_keeps_private_original_and_quarantine_diagnostic(admin_api):
    import json
    client,store,files,inspection=admin_api
    response=client.post('/api/admin/integrations/nfpa72/templates',files={'file':('short.pdf',template_bytes())})
    assert response.status_code==400
    originals=list(files.root.glob('_pdf_integrations/nfpa72/*/original.pdf'))
    assert len(originals)==1 and originals[0].read_bytes()==template_bytes()
    diagnostic=json.loads(originals[0].with_name('intake.json').read_text())
    assert diagnostic['status']=='quarantined' and diagnostic['error_code']=='INVENTORY_FAILED'
    with store() as session:assert session.query(PdfIntegrationVersion).count()==0


def test_admin_render_does_not_hold_up_existing_inspection_writes(admin_api,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from alarm_inspection.integrations import pdf_service
    from alarm_inspection.storage import Inspection
    client,store,files,inspection=admin_api
    draft=configured(client);path='/api/admin/integrations/versions/'+draft['id']
    original=pdf_service.bounded_pdf;started=Event();release=Event()
    def paused(*args,**kwargs):
        if len(args)>2 and args[2].startswith('render'):
            started.set()
            if not release.wait(10):raise RuntimeError('Test render was not released.')
        return original(*args,**kwargs)
    monkeypatch.setattr(pdf_service,'bounded_pdf',paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        render=pool.submit(client.post,path+'/test',json={'inspection_id':inspection,'expected_revision':2})
        try:
            assert started.wait(5)
            def ordinary_save():
                with store.begin() as session:session.get(Inspection,inspection).address='Saved while PDF rendering is paused'
                return True
            assert pool.submit(ordinary_save).result(timeout=2)
        finally:release.set()
        response=render.result(timeout=10)
    assert response.status_code==200,response.text
    with store() as session:assert session.get(Inspection,inspection).address=='Saved while PDF rendering is paused'


def test_failed_admin_render_is_retained_and_never_downloadable(admin_api,monkeypatch):
    from alarm_inspection.integrations import pdf_service
    from alarm_inspection.integrations.pdf_models import PdfExportArtifact
    client,store,files,inspection=admin_api
    draft=configured(client);original=pdf_service.bounded_pdf
    def fail(*args,**kwargs):
        if len(args)>2 and args[2].startswith('render'):raise RuntimeError('Synthetic renderer failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(pdf_service,'bounded_pdf',fail)
    response=client.post('/api/admin/integrations/versions/'+draft['id']+'/test',json={'inspection_id':inspection,'expected_revision':2})
    assert response.status_code==503
    with store() as session:
        artifact=session.query(PdfExportArtifact).one()
        assert artifact.status=='failed' and artifact.error_code=='DIAGNOSTIC_FAILED'
        ident=artifact.id
    assert client.get('/api/admin/integrations/tests/'+ident).status_code==400


def test_mapped_manual_question_can_change_without_adopting_old_answer(admin_api):
    from alarm_inspection.domain.pdf_integrations import FormAnswer
    from alarm_inspection.integrations.pdf_repository import append_decision
    client,store,files,inspection=admin_api
    draft=configured(client);config=draft['config'];path='/api/admin/integrations/versions/'+draft['id']
    config['manual_inputs']=[dict(id='remarks',label='Remarks',meaning='Original question',type='text')]
    target=next(t for t in config['inventory']['targets'] if t['kind']=='text')
    config['mappings']=[dict(m,disposition='source',source={'kind':'manual','id':'remarks'}) if m['target_id']==target['id'] else m for m in config['mappings']]
    assert client.put(path,json={'config':config,'expected_revision':2}).status_code==200
    test=client.post(path+'/test',json={'inspection_id':inspection,'expected_revision':3}).json()
    assert client.post(path+'/publish',json={'inspection_id':inspection,'expected_revision':3,'integration_revision':1,
        'test_artifact_id':test['test_artifact_id'],'verified_target_ids':test['target_ids'],'confirmed':True,'change_summary':'Reviewed original question'}).status_code==200
    assert client.post('/api/admin/integrations/compliance/state',json={'expected_revision':2,'enabled':True}).status_code==200
    with store.begin() as session:append_decision(session,draft['id'],inspection,FormAnswer(input_id='remarks',value='Old answer'),actor_id='tech')
    copied=client.post(path+'/copy').json();config=copied['config'];config['manual_inputs'][0]['meaning']='Changed question requiring review'
    path='/api/admin/integrations/versions/'+copied['id']
    assert client.put(path,json={'config':config,'expected_revision':1}).status_code==200
    # Test the draft's current input schema, never the incompatible old answer.
    result=client.post(path+'/test',json={'inspection_id':inspection,'expected_revision':2})
    assert result.status_code==200,result.text
    assert result.json()['config_sha256']!=test['config_sha256']


def test_compact_diagnostic_vectors_cover_all_choices_and_duplicate_occurrences(admin_api):
    client,store,files,inspection=admin_api
    draft=configured(client);config=draft['config'];path='/api/admin/integrations/versions/'+draft['id']
    config['manual_inputs']=[dict(id='first',label='First independent cell',meaning='Actual first value',type='dropdown',options=['A','B']),
                             dict(id='second',label='Second independent cell',meaning='Actual second value',type='dropdown',options=['0','1','2'])]
    targets=[t for t in config['inventory']['targets'] if t['kind']=='text']
    for index,target in enumerate(targets):
        config['mappings']=[dict(m,disposition='source',source={'kind':'manual','id':'first' if index==0 else 'second'}) if m['target_id']==target['id'] else m for m in config['mappings']]
    assert client.put(path,json={'config':config,'expected_revision':2}).status_code==200
    result=client.post(path+'/test',json={'inspection_id':inspection,'expected_revision':3})
    assert result.status_code==200,result.text
    assert result.json()['scenario_count']==3
    pages=PdfReader(BytesIO(client.get('/api/admin/integrations/tests/'+result.json()['test_artifact_id']).content)).pages
    lines=[page.extract_text().splitlines() for page in pages]
    assert all(first in line and second in line for line,first,second in zip(lines,['A','B','A'],['0','1','2']))
