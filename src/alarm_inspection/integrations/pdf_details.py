"""Append-only Form Details and explicit inspection-specific scope decisions."""
import json
from sqlalchemy import select, text
from alarm_inspection.domain.pdf_integrations import FormAnswer, SourceRef, canonical_json, payload_hash
from alarm_inspection.domain.pdf_readiness import evaluate_snapshot
from alarm_inspection.integrations import pdf_repository as repo
from alarm_inspection.integrations.pdf_models import PdfIntegration, PdfIntegrationVersion, PdfIntegrationAuditEntry, InspectionFormDecision
from alarm_inspection.integrations.pdf_sources import capture_snapshot, _catalog
from alarm_inspection.storage import Inspection


def policy_hash(config):
    return payload_hash({'applicability':config.applicability,'reason':config.applicability_reason,'categories':config.categories})


def saved_scope(session, inspection_id, key):
    rows=session.scalars(select(PdfIntegrationAuditEntry).where(PdfIntegrationAuditEntry.integration_key==key,
        PdfIntegrationAuditEntry.action=='form_scope_decision').order_by(PdfIntegrationAuditEntry.decided_at.desc(),PdfIntegrationAuditEntry.id.desc()))
    for row in rows:
        detail=json.loads(row.details_json)
        if detail['inspection_id']==inspection_id: return row.id,detail
    return '',None


def scope(store, inspection_id, key, actor_id):
    with store() as session:
        repo._actor(session,actor_id);repo._inspection(session,inspection_id)
        revision,decision=saved_scope(session,inspection_id,key)
        integration=session.get(PdfIntegration,key)
        config=repo._version(session,integration.active_version_id)[1] if integration and integration.active_version_id else None
        compatible=decision is None or config is not None and decision['policy_hash']==policy_hash(config)
        return revision,(decision['panel_ids'] if decision and compatible else []),not compatible


def details(store, inspection_id, key, *, actor_id):
    revision,panels,scope_changed=scope(store,inspection_id,key,actor_id)
    snapshot=capture_snapshot(store,inspection_id,key,actor_id=actor_id,panel_ids=panels)
    result=evaluate_snapshot(snapshot);config=snapshot.config
    fields=[]
    if config:
        with store() as session:
            for definition in config.manual_inputs:
                scopes=[None] if definition.scope=='inspection' else panels
                for index,panel in enumerate(scopes):
                    value=snapshot.manual_values[definition.id][index]
                    decision=session.get(InspectionFormDecision,value.provenance[0].decision_id) if value.provenance else None
                    answer=FormAnswer.model_validate_json(decision.answer_json) if decision else None
                    fields.append({'definition':definition.model_dump(mode='json'),'panel_id':panel,'source':value.model_dump(mode='json'),
                                   'override':answer.model_dump(mode='json') if answer and answer.override else None})
    return {'key':key,'version_id':config.version_id if config else None,'config_sha256':snapshot.stored_config_sha256,
        'scope_revision':revision,'panel_ids':panels,'scope_changed':scope_changed,'panels':snapshot.panel_choices,
        'applicability':config.applicability if config else None,'categories':config.categories if config else [],
        'signature_policy':config.signature_policy if config else None,'supplemental_policy':config.supplemental_policy if config else None,
        'fields':fields,'catalog':_catalog(snapshot),'readiness':result.model_dump(mode='json'),
        'export_available':False,'export_reason':'Completed PDF previews and downloads are not available yet. Form Details can be saved now.'}


def lock(session, inspection_id, key, actor_id):
    if session.get_bind().dialect.name=='sqlite': session.execute(text('BEGIN IMMEDIATE'))
    repo._actor(session,actor_id);repo._inspection(session,inspection_id)
    session.execute(select(Inspection).where(Inspection.id==inspection_id).with_for_update()).scalar_one()
    integration=session.execute(select(PdfIntegration).where(PdfIntegration.key==key).with_for_update()).scalar_one_or_none()
    if integration is None or not integration.enabled or not integration.active_version_id: raise ValueError('Integration unavailable.')
    row,config=repo._version(session,integration.active_version_id)
    if row.status!='published': raise ValueError('Published configuration required.')
    return config


def save_scope(store, inspection_id, key, payload, *, actor_id):
    with store.begin() as session:
        config=lock(session,inspection_id,key,actor_id)
        revision,_=saved_scope(session,inspection_id,key)
        if payload.get('version_id')!=config.version_id or payload.get('expected_revision')!=revision:
            raise repo.ConflictError('Scope or published configuration changed. Reload and review your selection.')
        panels=payload.get('panel_ids')
        snapshot=capture_snapshot(store,inspection_id,key,actor_id=actor_id,panel_ids=panels)
        errors=[b.message for b in snapshot.blockers if b.code in {'INVALID_SCOPE','UNCONFIGURED','DISABLED'}]
        if errors: raise ValueError('\n'.join(errors))
        repo._audit(session,key,config.version_id,'form_scope_decision',actor_id,
                    {'inspection_id':inspection_id,'panel_ids':snapshot.panel_ids,'policy_hash':policy_hash(config)})
    return details(store,inspection_id,key,actor_id=actor_id)


def save_answer(store, inspection_id, key, payload, *, actor_id):
    answer=FormAnswer.model_validate(payload.get('answer'))
    with store.begin() as session:
        config=lock(session,inspection_id,key,actor_id)
        if payload.get('version_id')!=config.version_id: raise repo.ConflictError('Published input definitions changed. Reload and review this answer.')
        _,selection=saved_scope(session,inspection_id,key)
        panels=selection['panel_ids'] if selection and selection['policy_hash']==policy_hash(config) else []
        snapshot=capture_snapshot(store,inspection_id,key,actor_id=actor_id,panel_ids=panels)
        definition=next((i for i in config.manual_inputs if i.id==answer.input_id),None)
        if definition is None: raise ValueError('Unknown input definition.')
        panel=payload.get('panel_id')
        scopes=[None] if definition.scope=='inspection' else panels
        if panel not in scopes: raise ValueError('Select and save explicit panel scope before answering.')
        current=snapshot.manual_values[definition.id][scopes.index(panel)]
        if payload.get('expected_fingerprint')!=current.fingerprint: raise repo.ConflictError('This answer changed on another device. Reload to compare before saving.')
        if answer.override:
            ref=answer.overridden_source
            if ref is None or ref==SourceRef(kind='manual',id=answer.input_id): raise ValueError('Select the actual distinct source being overridden.')
            source=snapshot.resolve(ref)
            if source.state!='ready' or source.fingerprint!=answer.source_fingerprint or canonical_json(source.value)!=canonical_json(answer.original_value):
                raise repo.ConflictError('Original source changed. Review the override again.')
        elif answer.overridden_source is not None or answer.source_fingerprint is not None:
            raise ValueError('Ordinary answers cannot carry override evidence.')
        repo.append_decision(session,config.version_id,inspection_id,answer,actor_id=actor_id,point_list_id=panel)
    return details(store,inspection_id,key,actor_id=actor_id)
