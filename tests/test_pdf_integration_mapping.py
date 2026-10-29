"""Deterministic rules: No is an answer, zero is data, missing is neither."""
from copy import deepcopy
from decimal import Decimal

import pytest

from pdf_storage_fixtures import config_data
from alarm_inspection.domain.pdf_integrations import Condition, IntegrationConfig, SourceRef, TargetMapping, Transform, canonical_json, payload_hash
from alarm_inspection.domain.pdf_mapping import (
    SourceValue, MappingError, answered, apply_transforms, condition_matches, map_target,
    map_answer_group, count_approved_devices,
)


def value(data, kind='text', *, state='ready', ident='remarks'):
    return SourceValue(source=SourceRef(kind='manual', id=ident), type=kind, state=state,
                       value=data, fingerprint=payload_hash({'value':data,'type':kind,'state':state}))


def test_answered_preserves_zero_false_no_na_and_missing():
    assert all(answered(v) for v in (0, 0.0, False, 'No', 'NA', 'Failed', 'Not tested'))
    assert not any(answered(v) for v in (None, '', '  '))


def test_numeric_lookup_concat_and_type_aware_conditions():
    number = apply_transforms(value(1.005, 'number'), [Transform(kind='number', decimals=2)], lambda _: None)
    assert number.value == '1.01'
    assert apply_transforms(value(1.25,'number'),[Transform(kind='number')],lambda _:None).value == '1.25'
    choice = apply_transforms(value('No','yes_no_na'), [Transform(kind='lookup', lookup={canonical_json('No'):'FAIL'})], lambda _: None)
    assert choice.value == 'FAIL'
    other = SourceRef(kind='inspection', field='city')
    joined = apply_transforms(value('Store'), [Transform(kind='concat', sources=[other], separator=' / ')], lambda _: value('Example'))
    assert joined.value == 'Store / Example'
    condition = Condition(source=SourceRef(kind='manual', id='remarks'), operator='equals', expected=False)
    assert condition_matches(condition, lambda _: value(0, 'number')) is False
    with pytest.raises(MappingError): condition_matches(condition, lambda _: value(None, state='missing'))


def test_date_only_cannot_invent_time_and_timezone_conversion_is_explicit():
    with pytest.raises(MappingError):
        apply_transforms(value('2026-10-28', 'date'), [Transform(kind='time', format='%H:%M')], lambda _: None)
    with pytest.raises(MappingError):
        apply_transforms(value('2026-10-28', 'date'), [Transform(kind='date', format='%Y-%m-%d %H:%M')], lambda _: None)
    result = apply_transforms(value('2026-10-28T14:30:00+00:00', 'datetime'),
                              [Transform(kind='time', format='%H:%M', timezone='America/New_York')], lambda _: None)
    assert result.value == '10:30'


def test_text_fits_or_blocks_without_truncation():
    config = IntegrationConfig.model_validate(config_data())
    target = next(t for t in config.inventory.targets if t.kind == 'text')
    mapping = TargetMapping(target_id=target.id, disposition='source', source=SourceRef(kind='manual',id='remarks'))
    result = map_target(target, mapping, value(0, 'number'), lambda _: None)
    assert result.text == '0' and result.raw_value == 0
    with pytest.raises(MappingError, match='overflow'):
        map_target(target, mapping, value('x'*500), lambda _: None)
    with pytest.raises(MappingError, match='character'):
        map_target(target, mapping, value('\u6f22'), lambda _: None)


def test_explicit_blank_policy_does_not_hide_changed_sources():
    config = IntegrationConfig.model_validate(config_data())
    target = next(t for t in config.inventory.targets if t.kind == 'text')
    mapping = TargetMapping(target_id=target.id, disposition='source', source=SourceRef(kind='manual',id='remarks'),
                            missing='blank', reason='Explicitly optional')
    assert map_target(target, mapping, value(None,state='missing'), lambda _: None).text == ''
    with pytest.raises(MappingError): map_target(target, mapping, value('Old',state='changed'), lambda _: None)


def test_answer_group_clears_unselected_states_and_rejects_missing_na_policy():
    raw = config_data(); original = next(t for t in raw['inventory']['targets'] if t['kind']=='checkbox')
    clone = deepcopy(original); clone['id'] = 'f'*64; clone['occurrence'] = 999
    raw['inventory']['targets'].append(clone)
    ref = {'kind':'manual','id':'result'}
    raw['manual_inputs'].append({'id':'result','label':'Functional result','meaning':'Explicit result','type':'yes_no_na'})
    for target in (original, clone):
        raw['mappings'] = [m for m in raw['mappings'] if m['target_id'] != target['id']]
        raw['mappings'].append({'target_id':target['id'],'disposition':'source','source':ref})
    raw['answer_groups'] = [{'id':'results','members':{'Yes':[original['id']], 'No':[clone['id']]},'required':True}]
    config = IntegrationConfig.model_validate(raw)
    result = map_answer_group(config, config.answer_groups[0], lambda _: value('No','yes_no_na'))
    assert result[original['id']].pdf_state == '/Off'
    assert result[clone['id']].pdf_state == '/Yes'
    with pytest.raises(MappingError): map_answer_group(config, config.answer_groups[0], lambda _: value('NA','yes_no_na'))


def test_count_requires_explicit_approved_classification_and_results():
    facts = [{'point_id':'p1','panel_id':'panel','classification_id':'doors','classification_approved':True,
              'result_approved':True,'test_result':'Fail','accepted_timestamp':'2026-10-28T10:00:00'}]
    assert count_approved_devices(facts, 'doors', 'installed') == 1
    assert count_approved_devices(facts, 'doors', 'tested_good') == 0
    with pytest.raises(ValueError): count_approved_devices([dict(facts[0],classification_approved=False)],'doors','installed')
    with pytest.raises(ValueError): count_approved_devices([dict(facts[0],result_approved=False)],'doors','tested_good')
    with pytest.raises(ValueError): count_approved_devices([dict(facts[0],classification_id=None)],'doors','installed')


def test_wrap_preserves_text_and_shrink_respects_minimum_readable_size():
    config=IntegrationConfig.model_validate(config_data())
    target=next(t for t in config.inventory.targets if t.kind=='text').model_copy(update={'rect':[0.0,0.0,70.0,80.0]})
    text='  Alpha   Beta Gamma Delta'
    mapping=TargetMapping(target_id=target.id,disposition='source',source=SourceRef(kind='manual',id='remarks'),overflow='wrap')
    result=map_target(target,mapping,value(text),lambda _:None)
    assert result.text==text and ''.join(result.lines)==text
    shrink=mapping.model_copy(update={'overflow':'shrink','font_size':12.0,'minimum_font_size':6.0})
    result=map_target(target,shrink,value('Short sentence'),lambda _:None)
    assert 6<=result.font_size<=12
    with pytest.raises(MappingError): map_target(target,shrink,value('x'*1000),lambda _:None)


def test_time_or_device_collections_cannot_be_converted_to_a_passing_result():
    data=[{'accepted_timestamp':'2026-10-28T10:00:00'}]
    with pytest.raises(MappingError):
        apply_transforms(value(data,'times'),[Transform(kind='lookup',lookup={canonical_json(data):'Yes'})],lambda _:None)
