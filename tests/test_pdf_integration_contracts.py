"""P2 contracts must reject executable, unknown, or ambiguous configuration."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from pdf_storage_fixtures import config_data
from alarm_inspection.domain.pdf_integrations import (
    FieldVerification, IntegrationConfig, FormAnswer, ManualInput, SourceRef, canonical_json, payload_hash,
)


def test_config_round_trip_preserves_private_inventory():
    raw = config_data()
    config = IntegrationConfig.model_validate(raw)
    assert IntegrationConfig.model_validate_json(config.model_dump_json()) == config
    assert config.inventory.source_sha256 == raw['inventory']['source_sha256']
    assert payload_hash(config) == payload_hash(IntegrationConfig.model_validate(deepcopy(raw)))


@pytest.mark.parametrize('version', [0, 2, True, '1'])
def test_unknown_or_coerced_schema_versions_fail(version):
    raw = config_data(); raw['schema_version'] = version
    with pytest.raises(ValidationError): IntegrationConfig.model_validate(raw)


def test_unknown_fields_transforms_sources_and_duplicate_targets_fail():
    raw = config_data(); raw['python_expression'] = 'run something'
    with pytest.raises(ValidationError): IntegrationConfig.model_validate(raw)
    with pytest.raises(ValidationError): SourceRef(kind='sql', field='SELECT 1')
    raw = config_data(); raw['mappings'][0]['transforms'] = [{'kind': 'python', 'code': 'eval'}]
    with pytest.raises(ValidationError): IntegrationConfig.model_validate(raw)
    raw = config_data(); raw['mappings'].append(deepcopy(raw['mappings'][0]))
    with pytest.raises(ValidationError): IntegrationConfig.model_validate(raw)


def test_missing_unavailable_and_cross_version_sources_fail():
    raw = config_data(); raw['original']['key'] = '../original.pdf'
    with pytest.raises(ValidationError): IntegrationConfig.model_validate(raw)
    raw = config_data(); raw['mappings'][0].update(disposition='source', source={'kind': 'manual', 'id': 'unknown'})
    with pytest.raises(ValidationError): IntegrationConfig.model_validate(raw)


@pytest.mark.parametrize('value', [0, 1.25])
def test_numbers_remain_numbers_and_boolean_is_not_a_number(value):
    definition = ManualInput(id='reading', label='Voltage', meaning='Measured main supply voltage', type='number')
    answer = FormAnswer(input_id='reading', value=value)
    definition.validate_value(answer.value)
    assert type(answer.value) is type(value)
    with pytest.raises(ValueError): definition.validate_value(False)


def test_negative_answers_and_cleared_values_are_distinct_and_overrides_require_reason():
    definition = ManualInput(id='result', label='Test', meaning='Explicit functional test', type='yes_no_na')
    for value in ('Yes', 'No', 'NA', None): definition.validate_value(FormAnswer(input_id='result', value=value).value)
    with pytest.raises(ValueError): definition.validate_value(False)
    with pytest.raises(ValidationError): FormAnswer(input_id='result', value='No', override=True)
    answer = FormAnswer(input_id='result', value='No', override=True, reason='Reviewed correction',
                        source_fingerprint='a' * 64, original_value='Yes')
    assert '"No"' in canonical_json(answer)


def test_datetime_requires_offset_and_semantic_hash_changes():
    a = ManualInput(id='when', label='Time', meaning='Monitoring notification time', type='datetime')
    a.validate_value('2026-10-28T10:00:00-04:00')
    with pytest.raises(ValueError): a.validate_value('2026-10-28T10:00:00')
    b = a.model_copy(update={'meaning': 'Restoration time'})
    assert payload_hash(a) != payload_hash(b)


def test_verification_timestamp_survives_strict_json_round_trip():
    from uuid import uuid4
    evidence = FieldVerification(target_id='a' * 64, verified_by='admin', verified_at=datetime.now(timezone.utc),
                                  test_artifact_id=str(uuid4()))
    assert FieldVerification.model_validate_json(evidence.model_dump_json()) == evidence
