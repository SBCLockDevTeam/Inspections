"""Frozen exports, stale/forged proofs, exact bytes and failure recovery."""
from datetime import timedelta
from io import BytesIO
from uuid import uuid4
import pytest
from pypdf import PdfReader
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from test_pdf_integration_storage import database
from test_pdf_integration_sources import custom_config
from alarm_inspection.domain.pdf_integrations import FormAnswer
from alarm_inspection.integrations.pdf_repository import ConflictError,append_decision,set_enabled
from alarm_inspection.integrations.pdf_models import PdfExportArtifact
from alarm_inspection.integrations import pdf_exports as exports
from alarm_inspection.storage import Inspection


def setup(database):
    def mutate(raw):
        raw['filename_policy']='completion_date_panel_id'
        target=next(t for t in raw['inventory']['targets'] if t['kind']=='text')
        raw['mappings']=[dict(m,disposition='source',source={'kind':'manual','id':'remarks'},required=True) if m['target_id']==target['id'] else m for m in raw['mappings']]
    store,config,inspection=custom_config(database,mutate)
    with store.begin() as session:append_decision(session,config.version_id,inspection,FormAnswer(input_id='remarks',value='ACTUAL No RESULT'),actor_id='tech')
    return store,config,inspection,database[1]


def make_preview(store,config,inspection,files):
    context=exports.frozen_snapshot(store,inspection,'compliance',actor_id='tech')
    return exports.preview(store,inspection,'compliance',exports.PreviewRequest(expected_version_id=config.version_id,
        expected_source_fingerprint=context.source_fingerprint),files=files,actor_id='tech')


def proof(preview,**changes):
    return exports.ConfirmationRequest.model_validate(dict(preview_id=preview['id'],confirmation_token=preview['confirmation_token'],
        preview_sha256=preview['sha256'],request_id=str(uuid4()),confirmed=True,**changes))


def test_preview_final_exact_pages_cleared_presets_and_idempotent_history(database):
    store,config,inspection,files=setup(database)
    preview=make_preview(store,config,inspection,files)
    data,_=exports.download(store,inspection,'compliance',preview['id'],files=files,actor_id='tech')
    text=''.join(p.extract_text() for p in PdfReader(BytesIO(data)).pages)
    assert 'DRAFT PREVIEW - NOT FINAL' in text and 'ACTUAL No RESULT' in text and 'OLD PRESET' not in text
    request=proof(preview)
    first=exports.confirm(store,inspection,'compliance',request,files=files,actor_id='tech')
    retry=exports.confirm(store,inspection,'compliance',request,files=files,actor_id='tech')
    assert first==retry and first['status']=='ready'
    data,_=exports.download(store,inspection,'compliance',first['id'],files=files,actor_id='admin')
    reader=PdfReader(BytesIO(data));text=''.join(p.extract_text() for p in reader.pages)
    assert len(reader.pages)==1 and 'DRAFT PREVIEW' not in text and 'FEASIBILITY' not in text
    assert 'ACTUAL No RESULT' in text and 'OLD PRESET' not in text
    assert '/AcroForm' not in reader.trailer['/Root'] and all('/Annots' not in p for p in reader.pages)
    assert first['filename']=='SYNTHETIC-Example,VA-Compliance Inspection-10-02-26.pdf'
    provenance=exports.provenance(store,inspection,'compliance',first['id'],actor_id='tech')
    assert provenance['snapshot']['provenance'][0]['decision_id']
    assert len(exports.history(store,inspection,'compliance',actor_id='tech')['exports'])==1
    other=exports.confirm(store,inspection,'compliance',proof(preview),files=files,actor_id='tech')
    assert other['id']!=first['id'] and other['sha256']==first['sha256']


def test_changed_sources_forged_proofs_and_wrong_owner_fail_closed(database):
    store,config,inspection,files=setup(database);preview=make_preview(store,config,inspection,files)
    for changed in ({'confirmation_token':'x'*43},{'preview_sha256':'a'*64},{'confirmed':False}):
        raw=proof(preview).model_dump();raw.update(changed)
        with pytest.raises((ValueError,ConflictError)):exports.confirm(store,inspection,'compliance',exports.ConfirmationRequest.model_validate(raw),files=files,actor_id='tech')
    with pytest.raises(PermissionError):exports.confirm(store,inspection,'compliance',proof(preview),files=files,actor_id='admin')
    with store.begin() as session:session.get(Inspection,inspection).city='Changed'
    with pytest.raises(ConflictError):exports.confirm(store,inspection,'compliance',proof(preview),files=files,actor_id='tech')
    assert exports.history(store,inspection,'compliance',actor_id='tech')['exports']==[]


def test_post_acceptance_edits_do_not_mix_frozen_output(database,monkeypatch):
    store,config,inspection,files=setup(database);preview=make_preview(store,config,inspection,files)
    original=exports.bounded_pdf
    def render(*args,**kwargs):
        with store.begin() as session:append_decision(session,config.version_id,inspection,FormAnswer(input_id='remarks',value='LATER EDIT'),actor_id='tech')
        return original(*args,**kwargs)
    monkeypatch.setattr(exports,'bounded_pdf',render)
    final=exports.confirm(store,inspection,'compliance',proof(preview),files=files,actor_id='tech')
    data,_=exports.download(store,inspection,'compliance',final['id'],files=files,actor_id='tech')
    text=PdfReader(BytesIO(data)).pages[0].extract_text()
    assert 'ACTUAL No RESULT' in text and 'LATER EDIT' not in text


def test_retained_download_survives_disable_but_new_confirmation_does_not(database,monkeypatch):
    store,config,inspection,files=setup(database);preview=make_preview(store,config,inspection,files);request=proof(preview)
    final=exports.confirm(store,inspection,'compliance',request,files=files,actor_id='tech')
    with store.begin() as session:set_enabled(session,'compliance',False,expected_revision=3,actor_id='admin')
    with pytest.raises(exports.ExportBlocked):exports.confirm(store,inspection,'compliance',proof(preview),files=files,actor_id='tech')
    monkeypatch.setenv('INSPECTIONS_PDF_INTEGRATIONS_ENABLED','false')
    assert exports.download(store,inspection,'compliance',final['id'],files=files,actor_id='tech')[0]
    assert exports.confirm(store,inspection,'compliance',request,files=files,actor_id='tech')['id']==final['id']


def test_finalization_db_failure_recovers_same_bytes_after_restart(database,monkeypatch):
    store,config,inspection,files=setup(database);preview=make_preview(store,config,inspection,files)
    from sqlalchemy.orm import Session
    original=Session.execute
    def fail(self,statement,*args,**kwargs):
        if getattr(statement,'is_update',False) and getattr(statement,'table',None).name=='pdf_export_artifacts' and 'sha256' in str(statement):
            raise SQLAlchemyError('Synthetic DB failure after file retention')
        return original(self,statement,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Session,'execute',fail)
        with pytest.raises(SQLAlchemyError):exports.confirm(store,inspection,'compliance',proof(preview),files=files,actor_id='tech')
    view=exports.history(store,inspection,'compliance',actor_id='tech')['exports'][0]
    assert view['status']=='pending'
    with pytest.raises(ValueError):exports.download(store,inspection,'compliance',view['id'],files=files,actor_id='tech')
    with store.begin() as session:
        # Recovery lease simulated at the clock, never by rewriting immutable records.
        created=session.get(PdfExportArtifact,view['id']).created_at
    monkeypatch.setattr(exports,'_now',lambda:exports._aware(created)+timedelta(minutes=3))
    recovered=exports.recover(store,inspection,'compliance',view['id'],files=files,actor_id='tech')
    assert recovered['status']=='ready' and recovered['id']==view['id']


def test_renderer_failure_is_not_downloadable_and_answers_survive(database,monkeypatch):
    store,config,inspection,files=setup(database);preview=make_preview(store,config,inspection,files)
    def fail(*args,**kwargs):raise RuntimeError('Synthetic renderer failure')
    monkeypatch.setattr(exports,'bounded_pdf',fail)
    with pytest.raises(RuntimeError):exports.confirm(store,inspection,'compliance',proof(preview),files=files,actor_id='tech')
    view=exports.history(store,inspection,'compliance',actor_id='tech')['exports'][0]
    assert view['status']=='failed'
    with pytest.raises(ValueError):exports.download(store,inspection,'compliance',view['id'],files=files,actor_id='tech')
    context=exports.frozen_snapshot(store,inspection,'compliance',actor_id='tech')
    assert any(value.get('text')=='ACTUAL No RESULT' for value in context.resolved_values.values())


def test_expired_preview_cleanup_preserves_final_and_original_bytes(database,monkeypatch):
    store,config,inspection,files=setup(database);preview=make_preview(store,config,inspection,files)
    final=exports.confirm(store,inspection,'compliance',proof(preview),files=files,actor_id='tech')
    with store() as session:created=session.get(PdfExportArtifact,preview['id']).created_at
    monkeypatch.setattr(exports,'_now',lambda:exports._aware(created)+timedelta(days=2))
    assert exports.cleanup_expired_previews(store,files=files,actor_id='admin')['expired_preview_ids']==[preview['id']]
    assert exports.cleanup_expired_previews(store,files=files,actor_id='admin')['expired_preview_ids']==[]
    assert files.read(config.original)
    assert exports.download(store,inspection,'compliance',final['id'],files=files,actor_id='tech')[0]
    with pytest.raises(ConflictError):exports.download(store,inspection,'compliance',preview['id'],files=files,actor_id='tech')


def test_concurrent_confirmation_requests_reserve_exactly_one_artifact(database):
    from concurrent.futures import ThreadPoolExecutor
    store,config,inspection,files=setup(database);preview=make_preview(store,config,inspection,files);request=proof(preview)
    def confirm():return exports.confirm(store,inspection,'compliance',request,files=files,actor_id='tech')
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:confirm(),range(2)))
    assert len({r['id'] for r in results})==1
    assert len(exports.history(store,inspection,'compliance',actor_id='tech')['exports'])==1


def test_tampered_ready_bytes_are_not_downloadable(database):
    store,config,inspection,files=setup(database);preview=make_preview(store,config,inspection,files)
    final=exports.confirm(store,inspection,'compliance',proof(preview),files=files,actor_id='tech')
    with store() as session:key=session.get(PdfExportArtifact,final['id']).file_key
    files._path(key).write_bytes(b'CORRUPTED')
    with pytest.raises(ValueError):exports.download(store,inspection,'compliance',final['id'],files=files,actor_id='tech')


def test_nfpa_export_includes_exactly_first_four_pages_and_no_excluded_answers(database):
    from pypdf import PdfWriter
    from pdf_integration_fixtures import synthetic_form
    from alarm_inspection.integrations.pdf_inventory import inspect_pdf
    from alarm_inspection.domain.pdf_integrations import IntegrationConfig,ArtifactContext
    from alarm_inspection.integrations.pdf_repository import create_draft,reserve_artifact,finish_artifact,seal_version,activate_version
    store,files,inspection,_=database
    source=PdfReader(BytesIO(synthetic_form()));writer=PdfWriter()
    for _ in range(4):writer.add_page(source.pages[0])
    writer.add_page(source.pages[2]);stream=BytesIO();writer.write(stream);data=stream.getvalue()
    ident=str(uuid4());receipt=files.put(files.template_key('nfpa72',ident,'original.pdf'),data)
    inventory=inspect_pdf(data,pages=(1,2,3,4))
    config=IntegrationConfig.model_validate(dict(integration_key='nfpa72',version_id=ident,original=receipt.model_dump(),inventory=inventory,
        mappings=[dict(target_id=t['id'],disposition='sign_later' if t['kind']=='signature' else 'blank',reason='Reviewed synthetic blank') for t in inventory['targets']],
        manual_inputs=[dict(id='supplemental',label='Separate sheets attached?',meaning='Explicit declaration',type='dropdown',options=['Yes','No'],required=True)],
        applicability='no_panel',applicability_reason='Synthetic export',signature_policy='later_signing',supplemental_policy='manual_declaration',
        supplemental_source={'kind':'manual','id':'supplemental'},filename_policy='completion_date_panel_id'))
    with store.begin() as session:
        create_draft(session,config,files=files,actor_id='admin')
        test,_=reserve_artifact(session,ident,inspection,ArtifactContext(source_fingerprint='a'*64),purpose='test',actor_id='admin')
        finish_artifact(session,test.id,files.put(test.file_key,b'SYNTHETIC TEST'),files=files,actor_id='admin')
        seal_version(session,ident,files=files,expected_revision=1,test_artifact_id=test.id,verified_target_ids=[t['id'] for t in inventory['targets']],actor_id='admin')
        activate_version(session,'nfpa72',ident,expected_revision=1,actor_id='admin')
        set_enabled(session,'nfpa72',True,expected_revision=2,actor_id='admin')
        append_decision(session,ident,inspection,FormAnswer(input_id='supplemental',value='No'),actor_id='tech')
    context=exports.frozen_snapshot(store,inspection,'nfpa72',actor_id='tech')
    preview=exports.preview(store,inspection,'nfpa72',exports.PreviewRequest(expected_version_id=ident,expected_source_fingerprint=context.source_fingerprint),files=files,actor_id='tech')
    final=exports.confirm(store,inspection,'nfpa72',proof(preview),files=files,actor_id='tech')
    data,_=exports.download(store,inspection,'nfpa72',final['id'],files=files,actor_id='tech')
    reader=PdfReader(BytesIO(data));assert len(reader.pages)==4
    assert all('EXCLUDED' not in page.extract_text() and 'OLD PRESET' not in page.extract_text() for page in reader.pages)
    assert b'EXCLUDED FIELD SECRET' not in data


def test_http_export_contract_authentication_forgery_headers_and_private_paths(database,monkeypatch):
    from fastapi import FastAPI,Request
    from fastapi.testclient import TestClient
    from alarm_inspection.api.routers import inspection_form_integrations
    from alarm_inspection.storage import User
    store,config,inspection,files=setup(database)
    monkeypatch.setattr(inspection_form_integrations,'UPLOAD_ROOT',files.root)
    app=FastAPI()
    @app.middleware('http')
    async def auth(request:Request,call_next):
        with store() as session:request.state.current_user=session.get(User,request.headers.get('x-actor','tech'))
        return await call_next(request)
    app.include_router(inspection_form_integrations.create_router(store));client=TestClient(app)
    path=f'/api/inspections/{inspection}/form-integrations/compliance'
    for method,suffix,body in [('post','/preview',{}),('post','/exports',{}),('get','/exports',None),('get','/exports/missing/download',None),('get','/exports/missing/provenance',None),('post','/exports/missing/recover',{})]:
        kwargs={'headers':{'x-actor':'missing'}}
        if body is not None:kwargs['json']=body
        assert getattr(client,method)(path+suffix,**kwargs).status_code==403
    context=exports.frozen_snapshot(store,inspection,'compliance',actor_id='tech')
    response=client.post(path+'/preview',json={'expected_version_id':config.version_id,'expected_source_fingerprint':context.source_fingerprint,'values':{'manufactured':'Yes'}})
    assert response.status_code==400
    preview=client.post(path+'/preview',json={'expected_version_id':config.version_id,'expected_source_fingerprint':context.source_fingerprint}).json()
    final=client.post(path+'/exports',json=proof(preview).model_dump()).json()
    data=client.get(path+f'/exports/{final["id"]}/download')
    assert data.status_code==200 and data.headers['content-disposition'].startswith('attachment;')
    assert data.headers['cache-control']=='no-store'
    audit=client.get(path+f'/exports/{final["id"]}/provenance').json()
    assert 'key' not in audit['snapshot']['export_metadata']['config']['original']
    assert 'file_key' not in audit['artifact']
    with store.begin() as session:session.get(Inspection,inspection).status='deleted'
    assert client.get(path+f'/exports/{final["id"]}/download').status_code==400
