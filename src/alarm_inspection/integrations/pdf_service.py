"""Administrative lifecycle. Diagnostic documents never authorize final exports."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import sys
from uuid import uuid4

from alarm_inspection.domain.pdf_integrations import IntegrationConfig, ArtifactContext, SourceRef, payload_hash, canonical_json
from alarm_inspection.domain.pdf_mapping import SourceValue
from alarm_inspection.domain.pdf_readiness import SavedSnapshot, evaluate_snapshot
from alarm_inspection.integrations.pdf_models import PdfIntegration, PdfIntegrationVersion, PdfExportArtifact, PdfIntegrationAuditEntry
from alarm_inspection.integrations import pdf_repository as repo
from alarm_inspection.integrations.pdf_probe_limits import _run_process
from alarm_inspection.integrations.pdf_sources import configuration_source_catalog


def bounded_pdf(data, pages, operation, *, targets=None, page=1):
    with tempfile.TemporaryDirectory(prefix='pdf-admin-') as directory:
        root=Path(directory); root.chmod(0o700)
        source=root/'source.pdf'; source.write_bytes(data)
        output=root/('result.png' if operation=='page' else 'result.bin')
        request=root/'request.json'
        request.write_text(json.dumps(dict(source=str(source),output=str(output),pages=pages,
                                          operation=operation,targets=targets or {},page=page)))
        _run_process([sys.executable,'-m','alarm_inspection.integrations.pdf_admin_worker',str(request)],wall_seconds=30)
        result=output.read_bytes()
        if len(result)>64*1024**2: raise ValueError('PDF operation output limit exceeded.')
        return json.loads(result) if operation=='inventory' else result


def intake(session, key, data, filename, *, files, actor_id):
    repo._actor(session,actor_id,admin=True)
    if key not in {'nfpa72','compliance'}: raise ValueError('Unknown integration.')
    if not filename or len(filename)>255 or any(c in filename for c in '/\\') or any(ord(c)<32 for c in filename) or not filename.lower().endswith('.pdf'):
        raise ValueError('Use a plain PDF filename.')
    if not data.startswith(b'%PDF-') or len(data)>40*1024**2: raise ValueError('Invalid PDF content or size.')
    ident=str(uuid4())
    # Immutable original is retained privately even when parsing fails (quarantine).
    receipt=files.put(files.template_key(key,ident,'original.pdf'),data)
    metadata={'filename':filename,'actor_id':actor_id,'sha256':receipt.sha256,'received_at':datetime.now(timezone.utc).isoformat()}
    try:
        inventory=bounded_pdf(data,[1,2,3,4] if key=='nfpa72' else [1],'inventory')
    except (ValueError,RuntimeError,OSError):
        files.record_intake(receipt,{**metadata,'status':'quarantined','error_code':'INVENTORY_FAILED'})
        raise
    files.record_intake(receipt,{**metadata,'status':'inventoried','diagnostics':inventory['diagnostics']})
    config=IntegrationConfig(integration_key=key,version_id=ident,original=receipt,inventory=inventory)
    row=repo.create_draft(session,config,files=files,actor_id=actor_id)
    repo._audit(session,key,ident,'template_intake',actor_id,{'filename':filename,'sha256':receipt.sha256})
    return row


def copy_draft(session, version_id, *, files, actor_id):
    repo._actor(session,actor_id,admin=True)
    _,config=repo._version(session,version_id)
    ident=str(uuid4()); data=files.read(config.original)
    receipt=files.put(files.template_key(config.integration_key,ident,'original.pdf'),data)
    raw=config.model_dump(mode='json'); raw.update(version_id=ident,original=receipt.model_dump())
    if config.normalized:
        raw['normalized']=files.put(files.template_key(config.integration_key,ident,'normalized.pdf'),files.read(config.normalized)).model_dump()
    row=repo.create_draft(session,IntegrationConfig.model_validate(raw),files=files,actor_id=actor_id)
    source_intake=session.query(PdfIntegrationAuditEntry).filter(PdfIntegrationAuditEntry.version_id==version_id,
        PdfIntegrationAuditEntry.action.in_(['template_intake','template_copied'])).first()
    repo._audit(session,config.integration_key,ident,'template_copied',actor_id,
        {'source_version_id':version_id,'sha256':receipt.sha256,'filename':json.loads(source_intake.details_json).get('filename') if source_intake else 'Retained original template'})
    return row


def _references(config):
    refs=[]
    for item in [*config.mappings,*config.manual_inputs,*config.answer_groups]:
        if getattr(item,'source',None): refs.append(item.source)
        if item.required_when: refs.append(item.required_when.source)
        for transform in getattr(item,'transforms',[]): refs.extend(transform.sources)
    if config.supplemental_source: refs.append(config.supplemental_source)
    return refs


def validate_configuration(config, catalog):
    targets={t.id:t for t in config.inventory.targets}; mappings={m.target_id:m for m in config.mappings}
    errors=[]
    if set(targets)!=set(mappings) or not targets: errors.append('Every target needs an explicit disposition.')
    if config.applicability is None or config.applicability!='no_panel' and not config.categories: errors.append('Review applicability and required panel categories.')
    if config.signature_policy=='unresolved' or config.supplemental_policy=='unresolved': errors.append('Resolve signature and supplemental policies.')
    if config.normalized: errors.append('Normalized derivatives require later verified renderer support.')
    entries={canonical_json(SourceRef.model_validate(e['source'])):e for e in catalog['entries']}
    refs=_references(config)
    for ref in refs:
        entry=entries.get(canonical_json(ref))
        if entry is None or entry['state']=='unavailable' or entry['state']=='changed' and ref.kind!='manual': errors.append('Source unavailable or incompatible: '+canonical_json(ref))
    grouped={ident for g in config.answer_groups for ids in g.members.values() for ident in ids}
    for ident,mapping in mappings.items():
        target=targets[ident]
        if target.kind in {'unknown','pushbutton'} and mapping.disposition not in {'blank','excluded'}: errors.append('Unsupported target: '+ident)
        if target.kind in {'checkbox','radio'} and mapping.disposition not in {'blank','excluded'} and ident not in grouped: errors.append('Result marks require an explicit answer group: '+ident)
        if mapping.disposition=='constant' and (target.kind!='text' or not mapping.reason.strip()): errors.append('Constants require a reviewed invariant reason and text destination: '+ident)
        if mapping.required and mapping.disposition in {'blank','excluded','sign_later'}: errors.append('Required target cannot be blank: '+ident)
    if config.applicability=='no_panel' and (any(i.scope=='panel' for i in config.manual_inputs) or any(r.kind in {'panel','count'} for r in refs)):
        errors.append('A no-panel policy cannot require panel inputs or sources.')
    if errors: raise ValueError('\n'.join(sorted(set(errors))))
    return entries


def test_draft(store, version_id, inspection_id, panel_ids, *, files, actor_id, expected_revision):
    catalog=configuration_source_catalog(store,inspection_id,version_id,actor_id=actor_id,panel_ids=panel_ids)
    with store.begin() as session:
        repo._actor(session,actor_id,admin=True); row,config=repo._version(session,version_id)
        if row.status!='draft' or row.revision!=expected_revision: raise repo.ConflictError('Draft changed before test.')
        entries=validate_configuration(config,catalog)
        relevant={canonical_json(ref) for ref in _references(config)} | {canonical_json(SourceRef(kind='manual',id=i.id)) for i in config.manual_inputs}
        entries={key:value for key,value in entries.items() if key in relevant}
        # Exhaust every declared source option independently; false/No/NA never
        # become passing marks. Each scenario is retained for visual review.
        base={}; variants=[]
        for key,entry in entries.items():
            typ=entry['type']; options=entry.get('options') or []
            definition=next((i for i in config.manual_inputs if canonical_json(SourceRef(kind='manual',id=i.id))==key),None)
            value={'text':'TEST','number':0,'date':'2026-10-28','datetime':'2026-10-28T12:30:00+00:00','yes_no_na':'No'}.get(typ,'TEST')
            if options: value=options[0]
            if definition and typ=='number': value=definition.minimum if definition.minimum is not None else min(0,definition.maximum or 0)
            base[key]=SourceValue(source=SourceRef.model_validate(entry['source']),type=typ,state='ready',value=value,fingerprint=payload_hash({'synthetic':key}))
            choices=['Yes','No','NA'] if typ=='yes_no_na' else options
            for choice in choices: variants.append((key,choice))
        scenarios=[base]
        for key,value in variants: scenarios.append({**base,key:base[key].model_copy(update={'value':value})})
        if len(variants)>255: raise ValueError('Diagnostic scenario limit exceeded; reduce independent choices.')
        outputs=[]; plan_bytes=0
        for sources in scenarios:
            snapshot=SavedSnapshot(inspection_id=inspection_id,config=config,sources=sources,
                manual_values={i.id:[sources[canonical_json(SourceRef(kind='manual',id=i.id))]] for i in config.manual_inputs})
            result=evaluate_snapshot(snapshot)
            if result.blockers: raise ValueError('\n'.join(b.message for b in result.blockers))
            output={key:value.model_dump(mode='json') for key,value in result.targets.items()}
            plan_bytes+=len(canonical_json(output).encode())
            if plan_bytes>16*1024**2: raise ValueError('Diagnostic plan exceeds the 16 MiB limit.')
            outputs.append(output)
        context=ArtifactContext(source_fingerprint=payload_hash(config),resolved_values={'diagnostic':{
            'pages':config.inventory.selected_pages,'scenario_count':len(outputs),'catalog_schema':catalog_schema(catalog)}})
        config_sha256=row.payload_sha256
        data=files.read(config.original)
    # Reserve briefly, then release the write lock before any PDF processing.
    # Diagnostic failures remain retained pending/failed records, never finals.
    from sqlalchemy import select, text
    with store.begin() as session:
        if session.get_bind().dialect.name=='sqlite': session.execute(text('BEGIN IMMEDIATE'))
        session.execute(select(PdfIntegrationVersion).where(PdfIntegrationVersion.id==version_id).with_for_update()).scalar_one()
        current,_=repo._version(session,version_id)
        if current.status!='draft' or current.revision!=expected_revision or current.payload_sha256!=config_sha256:
            raise repo.ConflictError('Draft changed before diagnostic reservation; retest the saved version.')
        artifact,_=repo.reserve_artifact(session,version_id,inspection_id,context,purpose='test',actor_id=actor_id,renderer_version='pdf-admin-1')
        artifact_id,file_key=artifact.id,artifact.file_key
    try:
        # Rendering and private file I/O do not hold a database write lock.
        rendered=bounded_pdf(data,config.inventory.selected_pages,'render_batch',targets=outputs)
        receipt=files.put(file_key,rendered)
        with store.begin() as session:
            repo.finish_artifact(session,artifact_id,receipt,files=files,actor_id=actor_id)
    except Exception:
        # A failed status update can leave a non-downloadable pending record;
        # originals and previously ready diagnostics are never removed.
        try:
            with store.begin() as session: repo.fail_artifact(session,artifact_id,'DIAGNOSTIC_FAILED',actor_id=actor_id)
        except (ValueError,RuntimeError,OSError): pass
        raise
    return {'test_artifact_id':artifact_id,'config_sha256':config_sha256,'pages':config.inventory.selected_pages,
            'scenario_count':len(outputs),'target_ids':list(outputs[0]),'diagnostics':config.inventory.diagnostics}



def catalog_schema(catalog):
    return payload_hash([{k:e.get(k) for k in ('source','type','options','unit')} for e in catalog['entries']])


def publish(session,version_id,*,files,actor_id,expected_revision,test_artifact_id,verified_target_ids,catalog):
    repo._actor(session,actor_id,admin=True); row,config=repo._version(session,version_id)
    validate_configuration(config,catalog)
    test=session.get(PdfExportArtifact,test_artifact_id)
    if test is None or test.renderer_version!='pdf-admin-1': raise ValueError('Run the mapping test before publication.')
    files.read(config.original)
    repo.read_artifact(session,test.id,files=files,actor_id=actor_id)
    diagnostic=ArtifactContext.model_validate_json(test.snapshot_json).resolved_values.get('diagnostic',{})
    if diagnostic.get('pages')!=config.inventory.selected_pages or diagnostic.get('catalog_schema')!=catalog_schema(catalog):
        raise ValueError('Source definitions changed; retest this draft.')
    repo.seal_version(session,version_id,files=files,actor_id=actor_id,expected_revision=expected_revision,
                      test_artifact_id=test_artifact_id,verified_target_ids=verified_target_ids)
