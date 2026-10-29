"""Saved additional decisions, explicit scope, concurrency and override boundaries."""
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest
from test_pdf_integration_storage import database
from test_pdf_integration_sources import custom_config
from alarm_inspection.integrations.pdf_details import details,save_scope,save_answer
from alarm_inspection.integrations.pdf_models import InspectionFormDecision
from alarm_inspection.integrations.pdf_repository import ConflictError
from alarm_inspection.storage import Inspection,User
from alarm_inspection.api.routers.inspection_form_integrations import create_router


def setup(database,mutate=lambda raw:None):
    def update(raw):
        raw['manual_inputs'][0]['required']=True
        mutate(raw)
    store,config,inspection=custom_config(database,update)
    return store,config,inspection


def payload(view,value,**extra):
    return {'version_id':view['version_id'],'answer':dict(input_id='remarks',value=value,**extra),
            'panel_id':None,'expected_fingerprint':view['fields'][0]['source']['fingerprint']}


def test_saved_details_are_append_only_with_conflicts_and_typed_validation(database):
    store,config,inspection=setup(database)
    view=details(store,inspection,'compliance',actor_id='tech')
    assert not view['readiness']['ready'] and view['fields'][0]['source']['state']=='missing'
    update=payload(view,'First saved answer')
    saved=save_answer(store,inspection,'compliance',update,actor_id='tech')
    assert saved['readiness']['ready'] and not saved['export_available']
    with pytest.raises(ConflictError):save_answer(store,inspection,'compliance',update,actor_id='tech')
    saved=save_answer(store,inspection,'compliance',payload(saved,None),actor_id='tech')
    assert not saved['readiness']['ready']
    with store() as session:assert session.query(InspectionFormDecision).count()==2
    with pytest.raises(ValueError):save_answer(store,inspection,'compliance',payload(saved,123),actor_id='tech')


def test_scope_is_saved_explicitly_and_foreign_or_omitted_scope_rejected(database):
    def mutate(raw):raw.update(applicability='panel',categories=['Fire']);raw['manual_inputs'][0]['scope']='panel'
    store,config,inspection=setup(database,mutate)
    view=details(store,inspection,'compliance',actor_id='tech')
    assert view['fields']==[] and not view['readiness']['ready']
    update={'version_id':config.version_id,'expected_revision':'','panel_ids':[]}
    for ids in ([],['foreign'],['panel','panel']):
        with pytest.raises(ValueError):save_scope(store,inspection,'compliance',{**update,'panel_ids':ids},actor_id='tech')
    saved=save_scope(store,inspection,'compliance',{**update,'panel_ids':['panel']},actor_id='tech')
    assert saved['panel_ids']==['panel'] and saved['scope_revision'] and saved['fields'][0]['panel_id']=='panel'
    with pytest.raises(ConflictError):save_scope(store,inspection,'compliance',{**update,'panel_ids':['panel']},actor_id='tech')
    answer=payload(saved,'Panel-specific answer');answer['panel_id']='panel'
    saved=save_answer(store,inspection,'compliance',answer,actor_id='tech')
    assert saved['fields'][0]['source']['value']=='Panel-specific answer'
    # Saving details does not accept pending point/event decisions.
    assert any(b['code']=='UNACCEPTED_EVENT' or b['navigation']=='points' for b in saved['readiness']['blockers'])


def test_overrides_require_actual_saved_source_and_become_stale(database):
    store,config,inspection=setup(database)
    view=details(store,inspection,'compliance',actor_id='tech')
    source=next(s for s in view['catalog']['entries'] if s['source']['field']=='store_number')
    update=payload(view,'Reviewed override',override=True,reason='Corrected on site',overridden_source=source['source'],
                   original_value=source['value'],source_fingerprint=source['fingerprint'])
    forged={**update,'answer':{**update['answer'],'original_value':'FORGED'}}
    with pytest.raises(ConflictError):save_answer(store,inspection,'compliance',forged,actor_id='tech')
    saved=save_answer(store,inspection,'compliance',update,actor_id='tech')
    assert saved['fields'][0]['override']['reason']=='Corrected on site'
    with store.begin() as session:session.get(Inspection,inspection).store_number='Changed'
    saved=details(store,inspection,'compliance',actor_id='tech')
    assert saved['fields'][0]['source']['state']=='changed' and not saved['readiness']['ready']


def test_two_sessions_cannot_silently_replace_same_saved_answer(database):
    store,config,inspection=setup(database)
    view=details(store,inspection,'compliance',actor_id='tech')
    def save(value):
        try:save_answer(store,inspection,'compliance',payload(view,value),actor_id='tech');return 'saved'
        except ConflictError:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(save,['Device A','Device B']))
    assert sorted(results)==['conflict','saved']
    with store() as session:assert session.query(InspectionFormDecision).count()==1


def test_inspection_api_authorization_deleted_and_feature_off_isolation(database,monkeypatch):
    store,config,inspection=setup(database)
    app=FastAPI()
    @app.middleware('http')
    async def auth(request:Request,call_next):
        with store() as session:request.state.current_user=session.get(User,request.headers.get('x-actor','tech'))
        return await call_next(request)
    app.include_router(create_router(store));client=TestClient(app);path=f'/api/inspections/{inspection}/form-integrations'
    assert client.get(path,headers={'x-actor':'missing'}).status_code==403
    view=client.get(path+'/compliance').json()
    assert client.put(path+'/compliance/answers',json=payload(view,'Saved through API')).status_code==200
    assert client.get(path).status_code==200
    monkeypatch.setenv('INSPECTIONS_PDF_INTEGRATIONS_ENABLED','false')
    assert client.get(path).status_code==503
    monkeypatch.setenv('INSPECTIONS_PDF_INTEGRATIONS_ENABLED','true')
    with store.begin() as session:session.get(Inspection,inspection).status='deleted'
    assert client.get(path).status_code==400


def test_changed_published_question_preserves_prior_decision_and_requires_review(database):
    from uuid import uuid4
    from alarm_inspection.domain.pdf_integrations import IntegrationConfig
    from alarm_inspection.integrations.pdf_repository import create_draft,activate_version,seal_version,reserve_artifact,finish_artifact
    from alarm_inspection.domain.pdf_integrations import ArtifactContext
    store,config,inspection=setup(database)
    view=details(store,inspection,'compliance',actor_id='tech')
    saved=save_answer(store,inspection,'compliance',payload(view,'Old question answer'),actor_id='tech')
    _,files,_,_=database;ident=str(uuid4());raw=config.model_dump(mode='json');raw['version_id']=ident
    raw['original']=files.put(files.template_key('compliance',ident,'original.pdf'),files.read(config.original)).model_dump()
    raw['manual_inputs'][0]['meaning']='A different business question requiring review'
    new=IntegrationConfig.model_validate(raw)
    with store.begin() as session:
        create_draft(session,new,files=files,actor_id='admin')
        artifact,_=reserve_artifact(session,ident,inspection,ArtifactContext(source_fingerprint='a'*64),purpose='test',actor_id='admin')
        finish_artifact(session,artifact.id,files.put(artifact.file_key,b'SYNTHETIC TEST'),files=files,actor_id='admin')
        seal_version(session,ident,files=files,expected_revision=1,test_artifact_id=artifact.id,verified_target_ids=[t.id for t in new.inventory.targets],actor_id='admin')
        activate_version(session,'compliance',ident,expected_revision=3,actor_id='admin')
    current=details(store,inspection,'compliance',actor_id='tech')
    assert current['fields'][0]['source']['value']=='Old question answer'
    assert current['fields'][0]['source']['state']=='changed' and not current['readiness']['ready']
    with pytest.raises(ConflictError):save_answer(store,inspection,'compliance',payload(saved,'Stale browser'),actor_id='tech')
    reviewed=save_answer(store,inspection,'compliance',payload(current,'Reviewed answer for new question'),actor_id='tech')
    assert reviewed['readiness']['ready']
    with store() as session:assert session.query(InspectionFormDecision).count()==2
