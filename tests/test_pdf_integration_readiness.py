"""Pure readiness gates independent of database/HTTP and legacy export behavior."""
from copy import deepcopy

import pytest

from pdf_storage_fixtures import config_data
from alarm_inspection.domain.pdf_integrations import IntegrationConfig, SourceRef, payload_hash
from alarm_inspection.domain.pdf_mapping import SourceValue
from alarm_inspection.domain.pdf_readiness import SavedSnapshot, evaluate_snapshot


def snapshot(raw):
    config=IntegrationConfig.model_validate(raw)
    return SavedSnapshot(inspection_id='synthetic',config=config,stored_config_sha256=payload_hash(config))


def test_incomplete_mapping_signature_and_static_result_gates():
    raw=config_data();raw['mappings'].pop()
    assert any(b.code=='UNCONFIGURED' for b in evaluate_snapshot(snapshot(raw)).blockers)
    raw=config_data();raw['signature_policy']='signed_required'
    assert any(b.code=='SIGNATURE_POLICY_UNRESOLVED' for b in evaluate_snapshot(snapshot(raw)).blockers)
    raw=config_data();button=next(t for t in raw['inventory']['targets'] if t['kind']=='checkbox')
    raw['mappings']=[dict(m,disposition='constant',constant=True) if m['target_id']==button['id'] else m for m in raw['mappings']]
    result=evaluate_snapshot(snapshot(raw))
    assert not result.ready
    with pytest.raises(ValueError):result.artifact_context()


def test_nfpa_supplemental_declaration_requires_an_actual_saved_yes_or_no():
    raw=config_data();raw['integration_key']='nfpa72'
    raw['original']['key']=raw['original']['key'].replace('/compliance/','/nfpa72/')
    raw['inventory']['selected_pages']=[1,2,3,4];raw['inventory']['source_page_count']=4
    raw['inventory']['pages']=[dict(raw['inventory']['pages'][0],number=i) for i in (1,2,3,4)]
    raw['manual_inputs'].append({'id':'supplemental','label':'Attached','meaning':'Supplemental sheets attached','type':'yes_no_na'})
    raw['supplemental_policy']='manual_declaration'
    snap=snapshot(raw)
    assert not evaluate_snapshot(snap).ready
    raw['supplemental_source']={'kind':'manual','id':'supplemental'}
    snap=snapshot(raw);ref=SourceRef(kind='manual',id='supplemental')
    from alarm_inspection.domain.pdf_integrations import canonical_json
    for answer,ready in [('No',True),('NA',False),('Yes',True)]:
        values={canonical_json(ref):SourceValue(source=ref,type='yes_no_na',state='ready',value=answer,fingerprint='a'*64)}
        result=evaluate_snapshot(snap.model_copy(update={'sources':values}))
        assert result.ready is ready


def test_normalized_geometry_controls_overflow_without_rewriting_original_target():
    raw=config_data();target=next(t for t in raw['inventory']['targets'] if t['kind']=='text')
    raw['mappings']=[dict(m,disposition='constant',constant='A long value') if m['target_id']==target['id'] else m for m in raw['mappings']]
    assert evaluate_snapshot(snapshot(raw)).ready
    raw['normalized']={'key':raw['original']['key'].replace('original.pdf','normalized.pdf'),'sha256':'a'*64,'size':10}
    raw['normalized_targets']={t['id']:{'page':1,'rect':t['rect']} for t in raw['inventory']['targets']}
    raw['normalized_targets'][target['id']]['rect']=[0.0,0.0,8.0,18.0]
    assert any(b.code=='OVERFLOW' for b in evaluate_snapshot(snapshot(raw)).blockers)
    assert target['rect']!=[0.0,0.0,8.0,18.0]


def test_admin_default_timezone_changes_formatting_without_inventing_a_time():
    from pdf_storage_fixtures import config_data
    from alarm_inspection.domain.pdf_integrations import IntegrationConfig,SourceRef,canonical_json
    from alarm_inspection.domain.pdf_mapping import SourceValue
    from alarm_inspection.domain.pdf_readiness import SavedSnapshot,evaluate_snapshot
    raw=config_data();raw['default_timezone']='America/New_York'
    raw['manual_inputs'][0]['type']='datetime'
    target=next(t for t in raw['inventory']['targets'] if t['kind']=='text')
    raw['mappings']=[dict(m,disposition='source',source={'kind':'manual','id':'remarks'},transforms=[{'kind':'time','format':'%H:%M'}]) if m['target_id']==target['id'] else m for m in raw['mappings']]
    config=IntegrationConfig.model_validate(raw);ref=SourceRef(kind='manual',id='remarks')
    source=SourceValue(source=ref,type='datetime',state='ready',value='2026-10-28T12:30:00+00:00',fingerprint='a'*64)
    result=evaluate_snapshot(SavedSnapshot(inspection_id='synthetic',config=config,sources={canonical_json(ref):source}))
    assert result.ready and result.targets[target['id']].text=='08:30'


def test_default_timezone_never_converts_date_only_sources_into_times():
    from pdf_storage_fixtures import config_data
    from alarm_inspection.domain.pdf_integrations import IntegrationConfig,SourceRef,canonical_json
    from alarm_inspection.domain.pdf_mapping import SourceValue
    from alarm_inspection.domain.pdf_readiness import SavedSnapshot,evaluate_snapshot
    raw=config_data();raw['default_timezone']='America/New_York'
    target=next(t for t in raw['inventory']['targets'] if t['kind']=='text')
    raw['mappings']=[dict(m,disposition='source',source={'kind':'inspection','field':'completion_date'},transforms=[{'kind':'date','format':'%m/%d/%Y'}]) if m['target_id']==target['id'] else m for m in raw['mappings']]
    config=IntegrationConfig.model_validate(raw);ref=SourceRef(kind='inspection',field='completion_date')
    source=SourceValue(source=ref,type='date',state='ready',value='2026-10-29',fingerprint='a'*64)
    result=evaluate_snapshot(SavedSnapshot(inspection_id='synthetic',config=config,sources={canonical_json(ref):source}))
    assert result.ready and result.targets[target['id']].text=='10/29/2026'
