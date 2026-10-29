"""Store/Check List mapping saves: validate, render proof, retain a new version.

The previous draft/published version is never edited. Rendering holds no database
write lock, and activation uses optimistic concurrency against the opened version.
"""
from math import floor
from uuid import uuid4
from pydantic import Field
from sqlalchemy import update
from alarm_inspection.domain.pdf_integrations import (
    Contract, Digest, TargetMapping, IntegrationConfig, SimpleVerificationEvidence,
    SourceRef, canonical_json, payload_hash,
)
from alarm_inspection.domain.pdf_mapping import SourceValue, answered
from alarm_inspection.domain.pdf_readiness import SavedSnapshot, evaluate_snapshot
from alarm_inspection.integrations import pdf_repository as repo
from alarm_inspection.integrations.pdf_models import PdfIntegration, PdfIntegrationVersion
from alarm_inspection.integrations.pdf_sources import definition_catalog
from alarm_inspection.integrations.pdf_service import bounded_pdf


class SaveMapping(Contract):
    expected_revision: int = Field(ge=1)
    integration_revision: int = Field(ge=1)
    source_catalog_sha256: Digest
    mappings: list[TargetMapping] = Field(max_length=5000)


def _base(session, ident, payload, actor_id):
    repo._actor(session,actor_id,admin=True)
    row,config=repo._version(session,ident)
    integration=session.get(PdfIntegration,config.integration_key,populate_existing=True)
    if row.revision!=payload.expected_revision or integration.revision!=payload.integration_revision:
        raise repo.ConflictError('The integration changed. Reload to compare before saving; your local edits are retained.')
    return config


def _configuration(base, payload, entries, receipt, ident):
    targets={t.id:t for t in base.inventory.targets}
    requested={m.target_id:m for m in payload.mappings}
    if len(requested)!=len(payload.mappings) or requested.keys()-targets.keys():
        raise ValueError('Duplicate or unknown PDF field.')
    mapped=[]
    for target in base.inventory.targets:
        m=requested.get(target.id)
        if m is None:
            m=TargetMapping(target_id=target.id,disposition='sign_later' if target.kind=='signature' else 'blank',reason='Left unmapped when saving the integration.')
        if m.required_when or m.disposition=='computed':
            raise ValueError('Choose one Store Data or Check List field for each PDF field.')
        if m.source:
            entry=entries.get(canonical_json(m.source))
            if entry is None: raise ValueError('Choose an active Store Data or Check List field.')
            if m.default_value is not None:
                typ=entry['type']; value=m.default_value
                if not answered(value): raise ValueError('Enter a default value or turn off Use default.')
                if typ in {'text','date','datetime','choice','yes_no_na'} and not isinstance(value,str): raise ValueError('This source needs a text default.')
                if entry.get('options') and value not in entry['options']: raise ValueError('Choose a valid default option.')
                if typ=='date':
                    from datetime import date
                    date.fromisoformat(value)
            if target.kind in {'checkbox','radio'} and (entry['type']!='yes_no_na' or m.check_on is None):
                raise ValueError('Map result marks to a Yes/No/NA Check List field and choose when to mark it.')
            m=m.model_copy(update={'source_schema_sha256':entry.get('schema_sha256')})
        if m.default_value is not None and not m.source: raise ValueError('A fallback default requires a mapped source. Use a fixed value for an unmapped text field.')
        if target.kind in {'checkbox','radio'} and m.disposition=='constant': raise ValueError('A fixed value cannot create a result mark.')
        if target.kind in {'unknown','pushbutton'} and m.disposition not in {'blank','excluded'}: raise ValueError('This PDF field cannot be populated.')
        if m.required and m.disposition in {'blank','excluded','sign_later'}: raise ValueError('A required field needs a source or fixed value.')
        if target.kind in {'text','choice'}:
            # Dense supplied forms have 8-point-high boxes. Fit the starting
            # font to actual geometry rather than forcing a 9/6-point preset.
            height_font=max(4, floor((target.rect[3]-target.rect[1]-2)/1.2*2)/2)
            font=min(m.font_size,height_font)
            m=m.model_copy(update={'font_size':font,'minimum_font_size':min(m.minimum_font_size,font)})
        mapped.append(m)
    raw=base.model_dump(mode='json')
    raw.update(version_id=ident,original=receipt.model_dump(mode='json'),mapping_mode='store_checklist',mappings=[m.model_dump(mode='json') for m in mapped],
        manual_inputs=[],answer_groups=[],applicability='no_panel',applicability_reason='These forms use only Store Data and Check List fields.',
        categories=[],signature_policy='later_signing',supplemental_policy='not_applicable',supplemental_source=None,filename_policy='completion_date_panel_id')
    return IntegrationConfig.model_validate(raw)


def _errors(config,result):
    targets={t.id:t for t in config.inventory.targets}
    mappings={m.target_id:m for m in config.mappings}
    return '\n'.join((f"Page {targets[b.target_id].page} · {mappings[b.target_id].label or targets[b.target_id].qualified_name}: " if b.target_id in targets else '')+b.message for b in result.blockers)


def save_mapping(store, version_id, raw, *, files, actor_id):
    payload=SaveMapping.model_validate(raw)
    with store() as session:
        base=_base(session,version_id,payload,actor_id)
        if base.normalized: raise ValueError('This template needs Debug review before simplified mapping.')
        catalog=definition_catalog(session,actor_id=actor_id)
        if payload.source_catalog_sha256 != catalog['schema_sha256']:
            raise repo.ConflictError('Check List fields changed. Reopen the integration to review the current fields.')
        original=files.read(base.original)
    ident=str(uuid4())
    receipt=files.put(files.template_key(base.integration_key,ident,'original.pdf'),original)
    entries={canonical_json(SourceRef.model_validate(e['source'])):e for e in catalog['entries']}
    config=_configuration(base,payload,entries,receipt,ident)
    plans=[]
    # Complete-form vectors cover every configured choice without relying on
    # an inspection's answers or storing customer data in the mapping proof.
    referenced={canonical_json(m.source) for m in config.mappings if m.source}
    used={key:entries[key] for key in referenced}
    count=max([len(e.get('options',[])) for e in used.values()]+[1])
    for index in range(count):
        sources={}
        for key,e in used.items():
            options=e.get('options') or []
            value=options[index%len(options)] if options else '2026-10-29' if e['type']=='date' else 'T'
            sources[key]=SourceValue(source=SourceRef.model_validate(e['source']),type=e['type'],value=value,state='ready',fingerprint=payload_hash({'test':key,'value':value}))
        result=evaluate_snapshot(SavedSnapshot(inspection_id='mapping-proof',config=config,sources=sources,catalog_metadata=used))
        if not result.ready: raise ValueError(_errors(config,result))
        plans.append({key:value.model_dump(mode='json') for key,value in result.targets.items()})
    # Exercise configured fallback values too, so an invalid/overflowing default
    # fails at Save instead of waiting for an inspection with a missing answer.
    defaults={canonical_json(m.source) for m in config.mappings if m.source and m.default_value is not None}
    if defaults:
        missing={key:(value.model_copy(update={'state':'missing','value':None}) if key in defaults else value) for key,value in sources.items()}
        # Another mapping of the same source may require an answer with no
        # default. Make only that other mapping optional in the fallback proof.
        trial=config.model_copy(update={'mappings':[m.model_copy(update={
            'required':False,'missing':'blank','reason':'Diagnostic optional input.'})
            if m.source and canonical_json(m.source) in defaults and m.default_value is None else m for m in config.mappings]})
        result=evaluate_snapshot(SavedSnapshot(inspection_id='mapping-proof',config=trial,sources=missing,catalog_metadata=used))
        if not result.ready: raise ValueError('Default value: '+_errors(config,result))
        plans.append({key:value.model_dump(mode='json') for key,value in result.targets.items()})
    if len(canonical_json(plans).encode()) > 16*1024**2:
        raise ValueError('Mapping proof exceeds the 16 MiB diagnostic limit.')
    rendered=bounded_pdf(original,config.inventory.selected_pages,'render_batch',targets=plans)
    proof=files.put(files.template_key(config.integration_key,ident,'mapping-test.pdf'),rendered)
    files.read(proof)
    evidence=SimpleVerificationEvidence(payload_sha256=payload_hash(config),test_file=proof,
        target_ids=sorted(t.id for t in config.inventory.targets),verified_by=actor_id,verified_at=repo._now(),scenario_count=len(plans))
    with store.begin() as session:
        _base(session,version_id,payload,actor_id)
        # A checklist type/options change during rendering must not publish stale mappings.
        current=definition_catalog(session,actor_id=actor_id)
        if current!=catalog: raise repo.ConflictError('Check List fields changed while saving. Reload and review your mapping.')
        row=repo.create_draft(session,config,files=files,actor_id=actor_id)
        session.execute(update(PdfIntegrationVersion).where(PdfIntegrationVersion.id==ident,PdfIntegrationVersion.status=='draft')
            .values(status='published',revision=2,verification_json=canonical_json(evidence),updated_at=repo._now()))
        result=session.execute(update(PdfIntegration).where(PdfIntegration.key==config.integration_key,PdfIntegration.revision==payload.integration_revision)
            .values(active_version_id=ident,enabled=True,revision=payload.integration_revision+1))
        if result.rowcount!=1: raise repo.ConflictError('Integration changed before activation. Your edits are retained.')
        repo._audit(session,config.integration_key,ident,'simple_mapping_saved',actor_id,{
            'previous_version_id':version_id,'mapped_fields':sum(m.disposition in {'source','constant'} for m in config.mappings),
            'scope':'Store Data and Check List only','evidence':evidence.model_dump(mode='json')})
    return ident
