"""Read-only saved-source behavior on the same SQLite/PostgreSQL fixtures as P2."""
from datetime import datetime, timezone
import json

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from test_pdf_integration_storage import database, published
from pdf_storage_fixtures import config_data, template_bytes
from alarm_inspection.domain.pdf_integrations import ArtifactContext, FormAnswer, IntegrationConfig, SourceRef, canonical_json, payload_hash
from alarm_inspection.integrations.pdf_sources import (assess_readiness, capture_snapshot, read_snapshot_session,
    source_catalog, configuration_source_catalog)
from alarm_inspection.integrations.pdf_repository import (append_decision, set_enabled, create_draft, reserve_artifact,
    finish_artifact, seal_version, activate_version)
from alarm_inspection.integrations.pdf_models import PdfIntegrationVersion
from alarm_inspection.storage import Base, Inspection, InspectionTask, InspectionChecklistDecision, PointListDecision, PointListEventDate, PointList


def setup_config(database):
    store, files, ident, _ = database
    config = published(store, files, ident)
    with store.begin() as session: set_enabled(session,'compliance',True,expected_revision=2,actor_id='admin')
    return store, config, ident


def custom_config(database, mutate, *, old_payload=False):
    store, files, ident, _ = database
    raw = config_data(); mutate(raw)
    config = IntegrationConfig.model_validate(raw)
    files.put(config.original.key,template_bytes())
    with store.begin() as session:
        create_draft(session,config,files=files,actor_id='admin')
        revision = 1
        if old_payload:
            legacy = json.loads(session.get(PdfIntegrationVersion,config.version_id).payload_json)
            legacy.pop('supplemental_source',None)
            for mapping in legacy['mappings']:
                for key in ('missing','font_size','minimum_font_size'): mapping.pop(key,None)
                for transform in mapping['transforms']: transform.pop('sources',None)
            session.execute(text('UPDATE pdf_integration_versions SET payload_json=:p, payload_sha256=:h, revision=2 WHERE id=:id'),
                            {'p':canonical_json(legacy),'h':payload_hash(legacy),'id':config.version_id})
            revision = 2
        row, _ = reserve_artifact(session,config.version_id,ident,ArtifactContext(source_fingerprint='a'*64),purpose='test',actor_id='admin')
        finish_artifact(session,row.id,files.put(row.file_key,b'SYNTHETIC TEST'),files=files,actor_id='admin')
        seal_version(session,config.version_id,files=files,expected_revision=revision,test_artifact_id=row.id,
                     verified_target_ids=[t.id for t in config.inventory.targets],actor_id='admin')
        activate_version(session,'compliance',config.version_id,expected_revision=1,actor_id='admin')
        set_enabled(session,'compliance',True,expected_revision=2,actor_id='admin')
    return store, config, ident


def test_catalog_legacy_answers_stability_and_no_writes(database):
    store, config, ident = setup_config(database)
    def old_rows():
        with store.kw['bind'].connect() as connection:
            return {t.name:list(connection.execute(select(t).order_by(*t.primary_key.columns))) for t in Base.metadata.sorted_tables}
    before = old_rows()
    first = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    second = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    assert first.fingerprint == second.fingerprint
    assert first.resolve(SourceRef(kind='checklist',id='task')).value == 'No'
    assert first.resolve(SourceRef(kind='inspection',field='start_date')).type == 'date'
    assert old_rows() == before
    assert assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=[]).ready


def test_latest_unchecked_legacy_answer_stays_unanswered_and_type_changes_do_not_fall_back(database):
    store, config, ident = setup_config(database)
    with store.begin() as session:
        session.add(InspectionChecklistDecision(id='later',inspection_id=ident,task_id='task',task_text='Task',input_type='checkbox',
                                                value='',completed=False,decided_by='tech',decided_at=datetime.now(timezone.utc)))
    snapshot = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    assert snapshot.resolve(SourceRef(kind='checklist',id='task')).state == 'missing'
    with store.begin() as session: session.get(InspectionTask,'task').input_type='textbox'
    snapshot = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    assert snapshot.resolve(SourceRef(kind='checklist',id='task')).state == 'changed'


def test_manual_values_provenance_and_unrelated_task_changes(database):
    store, config, ident = setup_config(database)
    before = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    with store.begin() as session: session.get(InspectionTask,'task').text = 'Unmapped task renamed'
    assert capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[]).fingerprint == before.fingerprint
    with store.begin() as session: append_decision(session,config.version_id,ident,FormAnswer(input_id='remarks',value='Saved'),actor_id='tech')
    after = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    answer = after.resolve(SourceRef(kind='manual',id='remarks'))
    assert answer.value == 'Saved' and answer.provenance[0].decision_id
    assert after.fingerprint != before.fingerprint


def test_no_panel_policy_rejects_injected_scope_and_pending_is_not_accepted(database):
    store, config, ident = setup_config(database)
    result = assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=['panel'])
    assert not result.ready and any(b.code=='INVALID_SCOPE' for b in result.blockers)
    snapshot = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    count = snapshot.resolve(SourceRef(kind='count',field='tested_good',id='doors'))
    assert count.state == 'unavailable'


def test_read_session_rejects_actual_writes_and_returns_pool_connection_clean(database):
    store, _, _, _ = database
    with pytest.raises(DBAPIError) as error:
        with read_snapshot_session(store) as session:
            session.execute(text("UPDATE inspections SET city = 'forged'"))
    assert 'read-only' in str(error.value).lower() or 'readonly' in str(error.value).lower()
    with store.begin() as session:
        assert session.execute(text('SELECT city FROM inspections')).scalar_one() == 'Example'
        session.execute(text("UPDATE inspections SET city = 'Writable again'"))


def test_request_cannot_supply_values_or_change_actor_permissions(database):
    store, _, ident = setup_config(database)
    with pytest.raises(TypeError): assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=[],values={'forged':'yes'})
    with pytest.raises(PermissionError): capture_snapshot(store,ident,'compliance',actor_id='missing',panel_ids=[])


def test_panel_review_pending_matches_and_duplicates_use_saved_authoritative_data(database):
    def mutate(raw): raw.update(applicability='panel',categories=['Fire'])
    store, _, ident = custom_config(database,mutate)
    def check(): return assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=['panel'])
    assert any(b.code=='MISSING_ANSWER' for b in check().blockers)
    with store.begin() as session: session.get(PointListDecision,'point-2').accepted=True
    assert any(b.code=='UNACCEPTED_EVENT' for b in check().blockers)  # Pending row is insufficient.
    with store.begin() as session:
        session.add(PointListEventDate(id='accepted-second',inspection_id=ident,point_list_id='panel',point_address=2,
                                       event_timestamp=datetime(2026,10,1,12),source_filename='approved.xlsx'))
    assert check().ready
    with store.begin() as session:
        session.add(PointListEventDate(id='duplicate',inspection_id=ident,point_list_id='panel',point_address=2,
                                       event_timestamp=datetime(2026,10,1,13),source_filename='other.xlsx'))
    assert not check().ready


def test_inspection_scope_cannot_omit_required_panels_or_use_foreign_ids(database):
    def mutate(raw): raw.update(applicability='inspection',categories=['Fire'])
    store, _, ident = custom_config(database,mutate)
    with store.begin() as session:
        session.add(PointList(id='second-panel',inspection_id=ident,category='Fire',filename='test.xlsx',path='synthetic',accepted_at=datetime.now(timezone.utc)))
    for ids in ([],['panel'],['foreign'],['panel','panel']):
        result = assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=ids)
        assert not result.ready and any(b.code=='INVALID_SCOPE' for b in result.blockers)


def test_conditional_remarks_are_required_for_no_without_turning_no_into_pass(database):
    def mutate(raw):
        raw['manual_inputs'][0]['required_when']={'source':{'kind':'checklist','id':'task'},'operator':'equals','expected':'No'}
        target = next(t for t in raw['inventory']['targets'] if t['kind']=='text')
        raw['mappings']=[dict(m,disposition='source',source={'kind':'checklist','id':'task'},required=True)
                         if m['target_id']==target['id'] else m for m in raw['mappings']]
    store, config, ident = custom_config(database,mutate)
    result = assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=[])
    assert not result.ready and any(b.source_id=='remarks' and b.navigation=='form_details' for b in result.blockers)
    with store.begin() as session: append_decision(session,config.version_id,ident,FormAnswer(input_id='remarks',value='WO-EXAMPLE'),actor_id='tech')
    result = assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=[])
    assert result.ready and any(v.text=='No' for v in result.targets.values())


def test_overrides_bind_actual_source_and_become_stale_without_rewriting_decisions(database):
    store, config, ident = setup_config(database)
    ref = SourceRef(kind='inspection',field='store_number')
    source = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[]).resolve(ref)
    with store.begin() as session:
        append_decision(session,config.version_id,ident,FormAnswer(input_id='remarks',value='Override note',override=True,
            reason='Reviewed',source_fingerprint=source.fingerprint,original_value=source.value,overridden_source=ref),actor_id='tech')
    assert assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=[]).ready
    with store.begin() as session: session.get(Inspection,ident).store_number='CHANGED'
    result = assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=[])
    assert not result.ready and any(b.code=='SOURCE_CHANGED' for b in result.blockers)


def test_older_published_json_hash_is_preserved_when_loading_new_optional_defaults(database):
    store, config, ident = custom_config(database,lambda _:None,old_payload=True)
    with store() as session:
        row = session.get(PdfIntegrationVersion,config.version_id)
        before = (row.payload_json,row.payload_sha256)
        assert '"font_size"' not in row.payload_json
    assert assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=[]).ready
    with store() as session:
        row = session.get(PdfIntegrationVersion,config.version_id)
        assert (row.payload_json,row.payload_sha256)==before


def test_database_snapshot_remains_consistent_while_another_session_commits(database):
    store, _, ident = setup_config(database)
    if store.kw['bind'].dialect.name=='sqlite':
        with store.kw['bind'].connect() as connection:
            connection.exec_driver_sql('PRAGMA journal_mode=WAL'); connection.commit()
    with read_snapshot_session(store) as reader:
        row = reader.get(Inspection,ident)
        assert row.city=='Example'
        with store.begin() as writer: writer.get(Inspection,ident).city='Changed concurrently'
        reader.refresh(row)
        assert row.city=='Example'
    with store() as session: assert session.get(Inspection,ident).city=='Changed concurrently'


def test_catalog_labels_do_not_bind_answers_and_admin_can_configure_first_draft(database):
    from test_pdf_integration_storage import draft
    store, files, ident, _ = database
    config = draft(store,files)
    catalog = configuration_source_catalog(store,ident,config.version_id,actor_id='admin',panel_ids=[])
    task = next(entry for entry in catalog['entries'] if entry['source']=={'kind':'checklist','id':'task','field':None})
    assert task['type']=='yes_no_na' and task['value']=='No' and task['label']=='Synthetic task'
    assert catalog['blockers'] and catalog['panels'][0]['id']=='panel'
    with pytest.raises(PermissionError): configuration_source_catalog(store,ident,config.version_id,actor_id='tech')
    assert not assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=[]).ready


def test_relevant_task_definition_and_decision_changes_invalidate_snapshot(database):
    def mutate(raw):
        target = next(t for t in raw['inventory']['targets'] if t['kind']=='text')
        raw['mappings']=[dict(m,disposition='source',source={'kind':'checklist','id':'task'})
                         if m['target_id']==target['id'] else m for m in raw['mappings']]
    store, _, ident = custom_config(database,mutate)
    before = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    with store.begin() as session: session.get(InspectionTask,'task').text='Changed relevant definition'
    after = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    assert before.fingerprint != after.fingerprint
    with store.begin() as session:
        task = session.get(InspectionTask,'task'); task.input_type='dropdown'; task.options_json='["New choice"]'
    result = assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=[])
    assert not result.ready and any(b.code=='SOURCE_CHANGED' for b in result.blockers)


def test_removed_dropdown_choice_is_not_replaced(database):
    store, _, ident = setup_config(database)
    with store.begin() as session:
        task=session.get(InspectionTask,'task');task.input_type='dropdown';task.options_json='["Current"]'
        session.add(InspectionChecklistDecision(id='dropdown',inspection_id=ident,task_id='task',task_text='Task',input_type='dropdown',
                     value='Removed',options_json='["Removed"]',completed=True,decided_by='tech',decided_at=datetime.now(timezone.utc)))
    source=capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[]).resolve(SourceRef(kind='checklist',id='task'))
    assert source.state=='changed' and source.value=='Removed'


def test_zero_numeric_answer_stays_populated_and_clearing_does_not_reuse_old_value(database):
    def mutate(raw):
        raw['manual_inputs'][0].update(type='number',minimum=0,unit='devices')
        target=next(t for t in raw['inventory']['targets'] if t['kind']=='text')
        raw['mappings']=[dict(m,disposition='source',source={'kind':'manual','id':'remarks'},required=True)
                         if m['target_id']==target['id'] else m for m in raw['mappings']]
    store,config,ident=custom_config(database,mutate)
    with store.begin() as session: append_decision(session,config.version_id,ident,FormAnswer(input_id='remarks',value=0),actor_id='tech')
    result=assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=[])
    assert result.ready and any(target.text=='0' and target.raw_value==0 for target in result.targets.values())
    assert result.artifact_context().source_fingerprint==result.source_fingerprint
    with store.begin() as session: append_decision(session,config.version_id,ident,FormAnswer(input_id='remarks',value=None),actor_id='tech')
    result=assess_readiness(store,ident,'compliance',actor_id='tech',panel_ids=[])
    assert not result.ready and any(b.code=='MISSING_ANSWER' for b in result.blockers)


def test_shared_in_memory_pool_is_rejected_without_rolling_back_caller_edits():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine=create_engine('sqlite:///:memory:')
    with engine.begin() as connection: connection.execute(text('CREATE TABLE pending_test (value INTEGER)'))
    store=sessionmaker(bind=engine)
    with store() as writer:
        writer.execute(text('INSERT INTO pending_test VALUES (1)'))
        with pytest.raises(ValueError,match='independent connections'):
            with read_snapshot_session(store): pass
        assert writer.execute(text('SELECT COUNT(*) FROM pending_test')).scalar_one()==1
        writer.rollback()
    engine.dispose()


def test_task_defaults_match_inspection_values_and_preserve_explicit_clear(database):
    store, config, ident = setup_config(database)
    with store.begin() as session:
        session.query(InspectionChecklistDecision).filter_by(task_id='task').delete()
        session.get(InspectionTask,'task').default_value = 'NA'
    snapshot = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    source = snapshot.resolve(SourceRef(kind='checklist',id='task'))
    assert source.value == 'NA' and not source.provenance
    with store() as session:
        assert session.query(InspectionChecklistDecision).filter_by(task_id='task').count() == 0
    with store.begin() as session:
        session.add(InspectionChecklistDecision(id='explicit-clear',inspection_id=ident,task_id='task',task_text='Task',input_type='checkbox',
            value='',completed=False,decided_by='tech',decided_at=datetime.now(timezone.utc)))
    cleared = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    assert cleared.resolve(SourceRef(kind='checklist',id='task')).state == 'missing'
    assert cleared.resolve(SourceRef(kind='checklist',id='task')).fingerprint != source.fingerprint
    with store.begin() as session:
        session.get(InspectionTask,'task').input_type = 'textbox'
        session.get(InspectionTask,'task').default_value = 'Cannot hide changed type'
    changed = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    assert changed.resolve(SourceRef(kind='checklist',id='task')).state == 'changed'


def test_native_labels_keep_source_identity_and_defaults_never_replace_saved_properties(database):
    from alarm_inspection.inspection_fields import native_fields, save_native_field
    from alarm_inspection.integrations.pdf_sources import definition_catalog
    store, config, ident = setup_config(database)
    before = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    with store() as session:
        catalog_before = definition_catalog(session, actor_id='admin')
        fields = native_fields(session)
    field = next(field for field in fields if field['native_field']=='inspector_name')
    field.update(text='Lead Inspector',default_value='Office contact')
    with store.begin() as session: save_native_field(session,field)
    with store() as session: catalog_after = definition_catalog(session,actor_id='admin')
    entry = next(entry for entry in catalog_after['entries'] if entry['source'].get('field')=='inspector_name')
    assert entry['label']=='Lead Inspector' and entry['source']['kind']=='inspection'
    assert catalog_before['schema_sha256'] != catalog_after['schema_sha256']
    after = capture_snapshot(store,ident,'compliance',actor_id='tech',panel_ids=[])
    assert after.resolve(SourceRef(kind='inspection',field='inspector_name')).state=='missing'
    assert before.fingerprint == after.fingerprint
    with store() as session:
        assert session.get(Inspection,ident).inspector_name == ''
        assert session.query(InspectionTask).count()==1
