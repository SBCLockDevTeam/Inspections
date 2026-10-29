"""Unpublished setup candidates never adopt defaults, names or task guesses."""
from pdf_storage_fixtures import template_bytes
from alarm_inspection.integrations.pdf_setup import build_candidate
from alarm_inspection.domain.pdf_integrations import IntegrationConfig


def test_candidate_covers_occurrences_without_approving_defaults_or_coupling_names():
    config,review=build_candidate(template_bytes(),'compliance')
    assert len(config.mappings)==len(config.inventory.targets)==len(review)
    assert config.applicability is None and config.categories==[] and config.default_timezone is None
    assert config.signature_policy=='unresolved' and config.filename_policy=='unresolved'
    assert not any(m.disposition=='constant' for m in config.mappings)
    assert not any(item['verified'] for item in review)
    duplicates=[t for t in config.inventory.targets if t.same_name_targets]
    sources={m.target_id:m.source for m in config.mappings}
    assert len({sources[t.id].id for t in duplicates})==len(duplicates)
    assert all(i.meaning and not i.model_dump().get('default') for i in config.manual_inputs)


def test_timezone_is_adjustable_and_invalid_names_fail_validation():
    import pytest
    config,_=build_candidate(template_bytes(),'compliance')
    raw=config.model_dump(mode='json');raw['default_timezone']='America/Los_Angeles'
    assert IntegrationConfig.model_validate(raw).default_timezone=='America/Los_Angeles'
    raw['default_timezone']='not/a/real-zone'
    with pytest.raises(ValueError):IntegrationConfig.model_validate(raw)


from test_pdf_integration_storage import database

def test_installation_keeps_integrations_disabled_and_unpublished(database):
    from alarm_inspection.integrations.pdf_setup import install_candidate
    from alarm_inspection.integrations.pdf_models import PdfIntegration,PdfIntegrationVersion
    store,files,inspection,_=database
    config,review=build_candidate(template_bytes(),'compliance')
    with store.begin() as session:ident=install_candidate(session,config,template_bytes(),files=files,actor_id='admin')
    with store() as session:
        integration=session.get(PdfIntegration,'compliance');version=session.get(PdfIntegrationVersion,ident)
        assert not integration.enabled and integration.active_version_id is None
        assert version.status=='draft' and version.verification_json=='{}'
        saved=IntegrationConfig.model_validate_json(version.payload_json)
        assert saved.default_timezone is None and saved.categories==[] and saved.signature_policy=='unresolved'
        assert len(saved.mappings)==len(saved.inventory.targets)
