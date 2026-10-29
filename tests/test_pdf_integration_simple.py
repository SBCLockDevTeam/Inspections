"""Save-to-export mappings use only saved Store Data and Check List answers."""
from datetime import date, datetime, timezone
from io import BytesIO
from uuid import uuid4
import pytest
from pypdf import PdfReader
from test_pdf_integration_admin import admin_api, uploaded
from test_pdf_integration_storage import database
from test_pdf_integration_exports import proof
from alarm_inspection.integrations import pdf_exports as exports
from alarm_inspection.integrations.pdf_sources import capture_snapshot
from alarm_inspection.domain.pdf_readiness import evaluate_snapshot
from alarm_inspection.storage import Inspection, InspectionTask, InspectionChecklistDecision
from alarm_inspection.integrations.pdf_models import PdfIntegration, PdfIntegrationVersion


def save(client,draft,mappings,revision=1):
    return client.post('/api/admin/integrations/versions/'+draft['id']+'/save-integration',json={
        'expected_revision':draft['revision'],'integration_revision':revision,'source_catalog_sha256':client.get('/api/admin/integrations/sources').json()['schema_sha256'],'mappings':mappings})


def text_target(draft):return next(t for t in draft['config']['inventory']['targets'] if t['kind']=='text')


def test_picker_without_inspection_and_save_exports_each_inspections_data(admin_api):
    client,store,files,inspection=admin_api
    assert client.get('/api/admin/integrations/sources',headers={'x-actor':'tech'}).status_code==403
    catalog=client.get('/api/admin/integrations/sources').json()
    assert {e['source']['kind'] for e in catalog['entries']}=={'inspection','checklist'}
    assert {e['section'] for e in catalog['entries']}=={'Store Data','Check List'}
    draft=uploaded(client);target=text_target(draft)
    mapping={'target_id':target['id'],'disposition':'source','source':{'kind':'inspection','field':'start_date'},'required':True,
        'transforms':[{'kind':'date','format':'%m/%d/%Y'}]}
    response=save(client,draft,[mapping]);assert response.status_code==200,response.text
    active=response.json();assert active['status']=='published' and active['id']!=draft['id']
    with store() as session:
        integration=session.get(PdfIntegration,'compliance');assert integration.enabled and integration.active_version_id==active['id']
        assert session.get(PdfIntegrationVersion,draft['id']).payload_json==__import__('alarm_inspection.domain.pdf_integrations',fromlist=['canonical_json']).canonical_json(draft['config'])
    other=str(uuid4())
    with store.begin() as session:
        session.add(Inspection(id=other,store_number='OTHER',address='',city='Test',state='VA',start_date=date(2026,9,12),completion_date=date(2026,9,13),created_at=datetime.now(timezone.utc)))
    for ident,expected in [(inspection,'10/01/2026'),(other,'09/12/2026')]:
        context=exports.frozen_snapshot(store,ident,'compliance',actor_id='tech')
        assert context.panel_ids==[]  # unresolved Points List rows never gate these forms
        preview=exports.preview(store,ident,'compliance',exports.PreviewRequest(expected_version_id=active['id'],expected_source_fingerprint=context.source_fingerprint),files=files,actor_id='tech')
        final=exports.confirm(store,ident,'compliance',proof(preview),files=files,actor_id='tech')
        data,_=exports.download(store,ident,'compliance',final['id'],files=files,actor_id='tech')
        assert expected in PdfReader(BytesIO(data)).pages[0].extract_text()
    conflict=save(client,draft,[mapping]);assert conflict.status_code==409
    second=save(client,active,[{**mapping,'source':{'kind':'inspection','field':'completion_date'}}],revision=2)
    assert second.status_code==200,second.text
    with store() as session:assert session.get(PdfIntegrationVersion,active['id']).status=='published'


def test_required_default_no_na_and_changed_source(admin_api):
    client,store,files,inspection=admin_api;draft=uploaded(client);target=text_target(draft)
    m={'target_id':target['id'],'disposition':'source','source':{'kind':'checklist','id':'task'},'required':True,'default_value':'NA'}
    response=save(client,draft,[m]);assert response.status_code==200,response.text
    def result():return evaluate_snapshot(capture_snapshot(store,inspection,'compliance',actor_id='tech'))
    assert result().targets[target['id']].text=='No'
    with store.begin() as session:
        session.add(InspectionChecklistDecision(id=str(uuid4()),inspection_id=inspection,task_id='task',task_text='Synthetic task',value='',completed=False,decided_by='tech',decided_at=datetime.now(timezone.utc)))
    assert result().targets[target['id']].text=='NA'
    with store.begin() as session:session.get(InspectionTask,'task').input_type='textbox'
    assert not result().ready and any(b.code=='SOURCE_CHANGED' for b in result().blockers)


def test_required_without_default_and_checkbox_marks_never_infer_pass(admin_api):
    client,store,files,inspection=admin_api;draft=uploaded(client);target=text_target(draft)
    mark=next(t for t in draft['config']['inventory']['targets'] if t['kind']=='checkbox')
    source={'kind':'checklist','id':'task'}
    bad=save(client,draft,[{'target_id':mark['id'],'disposition':'source','source':source,'check_on':'Yes','default_value':'Yes'}])
    assert bad.status_code==400
    response=save(client,draft,[{'target_id':target['id'],'disposition':'source','source':source,'required':True},
        {'target_id':mark['id'],'disposition':'source','source':source,'check_on':'Yes','missing':'blank','reason':'Optional result.'}])
    assert response.status_code==200,response.text
    snapshot=capture_snapshot(store,inspection,'compliance',actor_id='tech');result=evaluate_snapshot(snapshot)
    assert result.ready and result.targets[mark['id']].checked is False
    with store.begin() as session:
        session.add(InspectionChecklistDecision(id=str(uuid4()),inspection_id=inspection,task_id='task',task_text='Synthetic task',value='',completed=False,decided_by='tech',decided_at=datetime.now(timezone.utc)))
    result=evaluate_snapshot(capture_snapshot(store,inspection,'compliance',actor_id='tech'))
    assert not result.ready and any(b.code=='MISSING_ANSWER' for b in result.blockers)


@pytest.mark.parametrize('source',[{'kind':'panel','field':'category'},{'kind':'manual','id':'remarks'},{'kind':'count','field':'installed','id':'devices'}])
def test_save_rejects_non_store_checklist_sources(admin_api,source):
    client,store,files,inspection=admin_api;draft=uploaded(client)
    response=save(client,draft,[{'target_id':text_target(draft)['id'],'disposition':'source','source':source}])
    assert response.status_code==400
    with store() as session:assert not session.get(PdfIntegration,'compliance').enabled


def test_nfpa_save_does_not_require_manual_declaration_or_inspection(admin_api):
    from pypdf import PdfWriter
    from pdf_storage_fixtures import template_bytes
    client,store,files,inspection=admin_api
    writer=PdfWriter()
    for _ in range(4):writer.add_page(PdfReader(BytesIO(template_bytes())).pages[0])
    stream=BytesIO();writer.write(stream)
    response=client.post('/api/admin/integrations/nfpa72/templates',files={'file':('synthetic-four.pdf',stream.getvalue())})
    assert response.status_code==200,response.text
    draft=response.json()
    with store.begin() as session:session.get(Inspection,inspection).status='deleted'
    response=save(client,draft,[])
    assert response.status_code==200,response.text
    config=response.json()['config']
    assert config['inventory']['selected_pages']==[1,2,3,4] and config['manual_inputs']==[]
    with store.begin() as session:session.get(Inspection,inspection).status='active'
    context=exports.frozen_snapshot(store,inspection,'nfpa72',actor_id='tech')
    preview=exports.preview(store,inspection,'nfpa72',exports.PreviewRequest(expected_version_id=config['version_id'],expected_source_fingerprint=context.source_fingerprint),files=files,actor_id='tech')
    data,_=exports.download(store,inspection,'nfpa72',preview['id'],files=files,actor_id='tech')
    assert len(PdfReader(BytesIO(data)).pages)==4


def test_stale_picker_definition_and_no_panel_event_reads(admin_api):
    from sqlalchemy import event
    client,store,files,inspection=admin_api;draft=uploaded(client)
    old=client.get('/api/admin/integrations/sources').json()['schema_sha256']
    with store.begin() as session:session.get(InspectionTask,'task').text='Renamed checklist field'
    response=client.post('/api/admin/integrations/versions/'+draft['id']+'/save-integration',json={
        'expected_revision':1,'integration_revision':1,'source_catalog_sha256':old,'mappings':[]})
    assert response.status_code==409
    response=save(client,draft,[]);assert response.status_code==200,response.text
    statements=[]
    def record(connection,cursor,statement,parameters,context,executemany):statements.append(statement.lower())
    event.listen(store.kw['bind'],'before_cursor_execute',record)
    try:
        snapshot=capture_snapshot(store,inspection,'compliance',actor_id='tech',panel_ids=['obsolete-panel'])
        assert evaluate_snapshot(snapshot).ready
    finally:event.remove(store.kw['bind'],'before_cursor_execute',record)
    forbidden=('point_lists','point_list_decisions','point_list_event_dates','point_list_pending_event_dates','inspection_form_decisions')
    assert not any(any('from '+table in sql for table in forbidden) for sql in statements)


def test_dense_date_field_uses_geometry_and_default_overflow_is_rejected(admin_api):
    from reportlab.pdfgen.canvas import Canvas
    client,store,files,inspection=admin_api
    stream=BytesIO();canvas=Canvas(stream,pagesize=(612,792))
    canvas.acroForm.textfield(name='inspection_date',x=100,y=700,width=74,height=8.2)
    canvas.showPage();canvas.save()
    draft=client.post('/api/admin/integrations/compliance/templates',files={'file':('dense.pdf',stream.getvalue())}).json()
    target=text_target(draft)
    mapping={'target_id':target['id'],'label':'Inspection date','disposition':'source','source':{'kind':'inspection','field':'start_date'},
        'transforms':[{'kind':'date','format':'%m/%d/%Y'}],'required':True}
    response=save(client,draft,[mapping]);assert response.status_code==200,response.text
    actual=response.json()['config']['mappings'][0]
    assert actual['font_size']==5 and actual['minimum_font_size']==5
    active=response.json()
    too_long={**mapping,'source':{'kind':'inspection','field':'inspector_name'},'transforms':[],'default_value':'UNREASONABLY LONG DEFAULT '*30}
    response=save(client,active,[too_long],revision=2)
    assert response.status_code==400 and 'Default value' in response.text and 'Inspection date' in response.text
    with store() as session:assert session.get(PdfIntegration,'compliance').active_version_id==active['id']
