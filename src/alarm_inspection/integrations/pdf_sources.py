"""Read-only saved source catalog and consistent snapshots for PDF integration.

No caller-supplied answers, event rows or configuration are accepted. Catalogs
contain private inspection values and must only be returned to authorized users.
"""
from contextlib import contextmanager
from datetime import date, datetime, timezone
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool, SingletonThreadPool

from alarm_inspection.domain.checklist import CHECKBOX_CHOICES, checkbox_value, validate_options
from alarm_inspection.domain.export import validate_export_rows
from alarm_inspection.domain.inspection_names import normalize_city, normalize_state
from alarm_inspection.domain.pdf_integrations import FormAnswer, SourceRef, SourceProvenance, canonical_json, payload_hash
from alarm_inspection.domain.pdf_mapping import SourceValue, answered
from alarm_inspection.domain.pdf_readiness import SavedSnapshot, evaluate_snapshot, issue
from alarm_inspection.integrations.pdf_feature import enabled
from alarm_inspection.integrations.pdf_models import InspectionFormDecision, PdfIntegration, PdfIntegrationVersion
from alarm_inspection.integrations.pdf_repository import _version
from alarm_inspection.storage import (
    Inspection, User, InspectionTask, InspectionChecklistDecision, PointList,
    PointListDecision, PointListEventDate, PointListPendingEventDate,
)


@contextmanager
def read_snapshot_session(store):
    """Use a new database-enforced read transaction; never flush a caller's edits."""
    engine = store.kw['bind']
    if isinstance(engine.pool,(StaticPool,SingletonThreadPool)):
        raise ValueError('Snapshot reads require independent connections; shared/in-memory pools are unsupported.')
    with engine.connect() as connection:
        sqlite = engine.dialect.name == 'sqlite'
        try:
            if sqlite:
                connection.exec_driver_sql('PRAGMA query_only=ON')
                connection.exec_driver_sql('BEGIN')
            elif engine.dialect.name == 'postgresql':
                connection = connection.execution_options(isolation_level='REPEATABLE READ')
                connection.begin()
                connection.exec_driver_sql('SET TRANSACTION READ ONLY')
            else: raise ValueError('Unsupported snapshot database.')
            with Session(bind=connection,autoflush=False,expire_on_commit=False,info=dict(store.kw.get('info',{}))) as session:
                yield session
        finally:
            connection.rollback()
            if sqlite:
                connection.exec_driver_sql('PRAGMA query_only=OFF')
                connection.commit()


def _json(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat() if value.utcoffset() is not None else value.isoformat()
    if isinstance(value,date): return value.isoformat()
    return value


def _row(row):
    return {column.name:_json(getattr(row,column.name)) for column in row.__table__.columns}


def _source(ref, kind, value, facts, *, state=None, message='', provenance=()):
    state = state or ('ready' if answered(value) else 'missing')
    return SourceValue(source=ref,type=kind,value=value,state=state,message=message,provenance=list(provenance),
                       fingerprint=payload_hash({'source':ref.model_dump(),'type':kind,'value':value,'state':state,'facts':facts}))


def _refs(config):
    refs = []
    for mapping in config.mappings:
        if mapping.source: refs.append(mapping.source)
        for transform in mapping.transforms: refs.extend(transform.sources)
    for item in [*config.mappings,*config.manual_inputs,*config.answer_groups]:
        if item.required_when: refs.append(item.required_when.source)
    if config.supplemental_source: refs.append(config.supplemental_source)
    return refs


def capture_snapshot(store, inspection_id, integration_key, *, actor_id, panel_ids=(), version_id=None) -> SavedSnapshot:
    with read_snapshot_session(store) as session:
        return capture_snapshot_session(session,inspection_id,integration_key,actor_id=actor_id,panel_ids=panel_ids,version_id=version_id)


def capture_snapshot_session(session, inspection_id, integration_key, *, actor_id, panel_ids=(), version_id=None):
    user = session.get(User,actor_id)
    if user is None or not user.is_active or user.force_password_reset: raise PermissionError('Authentication is required.')
    inspection = session.get(Inspection,inspection_id)
    if inspection is None or inspection.status == 'deleted': raise ValueError('Inspection is unavailable.')
    if not enabled() or not session.info.get('pdf_integrations_available'):
        return SavedSnapshot(inspection_id=inspection_id,blockers=[issue('PDF integrations are disabled/unavailable.','DISABLED')])
    if version_id is not None:
        if not user.is_admin: raise PermissionError('Configuration samples require administrator access.')
        version, config = _version(session,version_id)
        integration_key = version.integration_key
    if integration_key not in {'nfpa72','compliance'}:
        return SavedSnapshot(inspection_id=inspection_id,blockers=[issue('Unknown integration.','UNCONFIGURED')])
    integration = session.get(PdfIntegration,integration_key)
    if version_id is None and (integration is None or not integration.enabled or not integration.active_version_id):
        return SavedSnapshot(inspection_id=inspection_id,blockers=[issue('Integration is disabled or unconfigured.','DISABLED')])
    if version_id is None: version, config = _version(session,integration.active_version_id)
    blockers = []
    if version_id is not None:
        blockers.append(issue('Configuration samples are diagnostic and cannot approve an inspection export.','UNCONFIGURED'))
    if version.status != 'published' or version.integration_key != integration_key:
        blockers.append(issue('A published matching configuration is required.','UNCONFIGURED'))
    simple = config.mapping_mode == 'store_checklist'
    if simple: panel_ids = []
    valid_ids = isinstance(panel_ids,(list,tuple)) and all(isinstance(p,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,36}',p) for p in panel_ids)
    requested = sorted(set(panel_ids)) if valid_ids else []
    if not valid_ids or len(requested) != len(panel_ids): blockers.append(issue('Explicit panel scope contains invalid/duplicate IDs.','INVALID_SCOPE',navigation='points'))
    panels = [] if simple else list(session.scalars(select(PointList).where(PointList.inspection_id==inspection_id,PointList.deleted_at.is_(None)).order_by(PointList.id)))
    owned = {p.id:p for p in panels}
    selected = [owned[p] for p in requested if p in owned]
    if set(requested) - owned.keys(): blockers.append(issue('A selected panel is unavailable for this inspection.','INVALID_SCOPE',navigation='points'))
    eligible = sorted(p.id for p in panels if p.category in config.categories)
    if config.applicability == 'no_panel':
        if requested or not config.applicability_reason.strip(): blockers.append(issue('This reviewed no-panel form cannot use a panel scope.','INVALID_SCOPE',navigation='points'))
        if any(d.scope=='panel' for d in config.manual_inputs) or any(ref.kind in {'panel','count'} for ref in _refs(config)):
            blockers.append(issue('A no-panel policy cannot require panel data or counts.','INVALID_SCOPE',navigation='integrations'))
    elif config.applicability == 'panel':
        if len(requested)!=1 or not config.categories or any(p.category not in config.categories for p in selected):
            blockers.append(issue('Select exactly one panel of an explicitly configured category.','INVALID_SCOPE',navigation='points'))
    elif config.applicability == 'inspection':
        if not eligible or not config.categories or requested != eligible:
            blockers.append(issue('Select every required panel in the configured inspection-wide scope.','INVALID_SCOPE',navigation='points'))
    else: blockers.append(issue('Panel applicability requires review.','UNCONFIGURED'))
    sources, facts, manual_values, catalog = {}, {}, {}, {}
    facts['inspection'] = _row(inspection)
    facts['integration'] = {'key':integration.key,'enabled':integration.enabled,'active_version_id':integration.active_version_id,'revision':integration.revision}
    facts['mode'] = 'configuration_sample' if version_id is not None else 'inspection'
    facts['required_scope'] = eligible if config.applicability=='inspection' else requested
    if not simple and not (inspection.store_number.strip() and inspection.address.strip() and normalize_city(inspection.city or '') and normalize_state(inspection.state or '')):
        blockers.append(issue('Store number, address, city and valid state are required.','MISSING_ANSWER',navigation='store_data'))
    if not simple and inspection.completion_date < inspection.start_date:
        blockers.append(issue('Completion date cannot precede start date.','MISSING_ANSWER',navigation='store_data'))
    for field in ('store_number','store_type','address','city','state','inspector_name','start_date','completion_date'):
        ref = SourceRef(kind='inspection',field=field)
        value = _json(getattr(inspection,field))
        sources[canonical_json(ref)] = _source(ref,'date' if field.endswith('_date') else 'text',value,{'inspection':inspection.id,'field':field,'value':value})
        catalog[canonical_json(ref)] = {'label':'Inspection: '+field.replace('_',' '),'options':[],'unit':None}
    tasks = list(session.scalars(select(InspectionTask).order_by(InspectionTask.position,InspectionTask.id)))
    decisions = list(session.scalars(select(InspectionChecklistDecision).where(InspectionChecklistDecision.inspection_id==inspection_id)
        .order_by(InspectionChecklistDecision.decided_at.desc(),InspectionChecklistDecision.id.desc())))
    latest = {}
    for decision in decisions: latest.setdefault(decision.task_id,decision)
    for task in tasks:
        ref = SourceRef(kind='checklist',id=task.id); decision = latest.get(task.id)
        kind = {'checkbox':'yes_no_na','textbox':'text','dropdown':'choice'}.get(task.input_type,'text')
        raw = {'definition':_row(task),'decision':_row(decision) if decision else None}
        state, message, value = None, '', None
        try:
            options = json.loads(task.options_json or '[]')
            validate_options(task.input_type,options)
            valid_definition = True
        except (TypeError,ValueError,AttributeError):
            options, valid_definition = [], False
        if not task.active or not valid_definition or decision and decision.input_type != task.input_type:
            state, message = 'changed','Checklist source was deactivated or its input type changed.'
        elif decision:
            value = checkbox_value(decision.value,decision.completed) if task.input_type=='checkbox' else decision.value
            if task.input_type=='dropdown' and value and value not in options:
                state, message = 'changed','The saved dropdown choice was removed; explicit review is required.'
            if task.input_type=='checkbox' and value not in ('','Yes','No','NA'):
                state, message = 'changed','The saved checkbox answer is incompatible.'
        provenance = [SourceProvenance(source=ref,decision_id=decision.id,decided_by=decision.decided_by,
                        decided_at=decision.decided_at.replace(tzinfo=timezone.utc) if decision.decided_at.tzinfo is None else decision.decided_at)] if decision else []
        sources[canonical_json(ref)] = _source(ref,kind,value,raw,state=state,message=message,provenance=provenance)
        catalog[canonical_json(ref)] = {'label':task.text,'options':list(CHECKBOX_CHOICES) if task.input_type=='checkbox' else options,'unit':None,'schema_sha256':checklist_schema(task)}
    if simple:
        refs = _refs(config)
        facts['dependencies'] = {canonical_json(ref):sources[canonical_json(ref)].fingerprint if canonical_json(ref) in sources else None for ref in refs}
        return SavedSnapshot(inspection_id=inspection_id,config=config,stored_config_sha256=version.payload_sha256,
            panel_ids=[],facts=facts,sources=sources,catalog_metadata=catalog,blockers=blockers)
    panel_facts, point_values, time_values = [], [], []
    # No-panel policy intentionally has no point dependencies. Forged scopes
    # still produce a blocker and can never qualify for final generation.
    for panel in selected if config.applicability != 'no_panel' else []:
        points = list(session.scalars(select(PointListDecision).where(PointListDecision.inspection_id==inspection_id,
            PointListDecision.point_list_id==panel.id).order_by(PointListDecision.id)))
        times = list(session.scalars(select(PointListEventDate).where(PointListEventDate.inspection_id==inspection_id,
            PointListEventDate.point_list_id==panel.id).order_by(PointListEventDate.id)))
        pending = list(session.scalars(select(PointListPendingEventDate).where(PointListPendingEventDate.inspection_id==inspection_id,
            PointListPendingEventDate.point_list_id==panel.id).order_by(PointListPendingEventDate.point_address)))
        panel_facts.append({'panel':_row(panel),'points':[_row(p) for p in points],'accepted_times':[_row(t) for t in times],
                            'pending_times':[_row(t) for t in pending]})
        accepted = [p for p in points if p.accepted and not p.deleted]
        unresolved = [p for p in points if not p.accepted and not p.deleted]
        ref = SourceRef(kind='panel',field='accepted_points')
        for point in unresolved: blockers.append(issue('Resolve this saved Review row before export.','MISSING_ANSWER',source=ref,section=panel.category,navigation='points').model_copy(update={'source_id':point.id}))
        dates = {t.point_address:t.event_timestamp for t in times}
        if len(dates)!=len(times): blockers.append(issue('Duplicate accepted event mappings require correction.','UNACCEPTED_EVENT',source=ref,section=panel.category))
        if not accepted: blockers.append(issue(validate_export_rows([]),'MISSING_ANSWER',source=ref,section=panel.category))
        seen = set()
        for point in accepted:
            row = {'address':str(point.address) if point.address is not None else '', 'text':point.text,'location':point.location,
                   'event_date':_json(dates.get(point.address)) or ''}
            problem = validate_export_rows([row])
            if point.address in seen: problem = 'Duplicate accepted point addresses require review.'
            seen.add(point.address)
            if problem:
                blockers.append(issue(problem,'UNACCEPTED_EVENT' if not row['event_date'] else 'MISSING_ANSWER',source=ref,section=panel.category)
                                .model_copy(update={'source_id':point.id}))
        point_values.extend(_row(p) for p in accepted); time_values.extend(_row(t) for t in times)
    facts['panels'] = panel_facts
    for field, kind, value in [('id','text',selected[0].id if len(selected)==1 else None),
                                ('category','text',selected[0].category if len(selected)==1 else None),
                                ('accepted_points','points',point_values),('accepted_times','times',time_values)]:
        ref = SourceRef(kind='panel',field=field)
        unavailable = config.applicability=='no_panel' or not selected or field in {'id','category'} and len(selected)!=1
        sources[canonical_json(ref)] = _source(ref,kind,value,panel_facts,state='unavailable' if unavailable else 'ready',
            message='A compatible explicit panel scope is required.',
            provenance=[SourceProvenance(source=ref,evidence_ids=[row['id']]) for row in value] if kind in {'points','times'} else [])
        catalog[canonical_json(ref)] = {'label':'Selected panel: '+field.replace('_',' '),'options':[],'unit':None}
    manual_rows = list(session.scalars(select(InspectionFormDecision).join(PdfIntegrationVersion,
        InspectionFormDecision.version_id==PdfIntegrationVersion.id).where(InspectionFormDecision.inspection_id==inspection_id,
        PdfIntegrationVersion.integration_key==integration_key)
        .order_by(InspectionFormDecision.decided_at.desc(),InspectionFormDecision.id.desc())))
    manual_latest = {}
    for row in manual_rows: manual_latest.setdefault((row.input_id,row.point_list_id),row)
    manual_raw, overrides, scoped_values = {}, {}, {}
    for definition in config.manual_inputs:
        ref = SourceRef(kind='manual',id=definition.id)
        scopes = [None] if definition.scope=='inspection' else [p.id for p in selected]
        values = []
        for scope in scopes:
            row = manual_latest.get((definition.id,scope))
            raw = {'definition':definition.model_dump(mode='json'),'decision':_row(row) if row else None,'panel':scope}
            state, message, value, provenance = None, '', None, []
            if row:
                saved_version = session.get(PdfIntegrationVersion,row.version_id)
                answer = FormAnswer.model_validate_json(row.answer_json); value = answer.value
                if saved_version is None or saved_version.status!='published' or row.input_schema_sha256 != payload_hash(definition):
                    state,message = 'changed','Manual input definition changed; review the retained answer.'
                else:
                    try: definition.validate_value(value)
                    except ValueError: state,message = 'changed','The retained manual answer is incompatible.'
                provenance = [SourceProvenance(source=ref,decision_id=row.id,decided_by=row.decided_by,
                    decided_at=row.decided_at.replace(tzinfo=timezone.utc) if row.decided_at.tzinfo is None else row.decided_at)]
                if answer.override: overrides[(definition.id,scope)] = answer
            source_type = 'choice' if definition.type=='dropdown' else definition.type
            current = _source(ref,source_type,value,raw,state=state,message=message,provenance=provenance)
            values.append(current); scoped_values[(definition.id,scope)] = current
            manual_raw[f'{definition.id}:{scope}'] = raw
        manual_values[definition.id] = values
        sources[canonical_json(ref)] = values[0] if len(values)==1 else _source(ref,'choice' if definition.type=='dropdown' else definition.type,None,manual_raw,
            state='unavailable',message='This per-panel field requires an explicitly selected single panel.')
        catalog[canonical_json(ref)] = {'label':definition.label,'options':definition.options or (list(CHECKBOX_CHOICES) if definition.type=='yes_no_na' else []),'unit':definition.unit}
    facts['manual'] = manual_raw
    # An override records the identity and fingerprint of its actual source.
    # Legacy identity-less overrides are retained but require explicit review.
    visiting, checked = set(), set()
    def check_override(ident, scope):
        key = (ident,scope)
        if key in checked: return
        answer = overrides.get(key)
        if answer is None: checked.add(key); return
        ref = SourceRef(kind='manual',id=ident); old = scoped_values[key]
        changed = key in visiting or len(visiting)>=32 or answer.overridden_source is None
        visiting.add(key)
        if not changed:
            original_ref = answer.overridden_source
            if original_ref.kind=='manual':
                definition = next((d for d in config.manual_inputs if d.id==original_ref.id),None)
                other_scope = scope if definition and definition.scope=='panel' else None
                if (original_ref.id,other_scope) in scoped_values:
                    check_override(original_ref.id,other_scope)
                original = scoped_values.get((original_ref.id,other_scope))
            else: original = sources.get(canonical_json(original_ref))
            changed = (original is None or original.state in {'changed','unavailable'} or original.fingerprint!=answer.source_fingerprint
                       or canonical_json(original.value)!=canonical_json(answer.original_value))
        visiting.discard(key); checked.add(key)
        if changed:
            updated = old.model_copy(update={'state':'changed','message':'Override source changed or needs explicit source identification.'})
            scoped_values[key] = updated
    for ident,scope in overrides: check_override(ident,scope)
    for definition in config.manual_inputs:
        scopes = [None] if definition.scope=='inspection' else [p.id for p in selected]
        manual_values[definition.id] = [scoped_values[(definition.id,scope)] for scope in scopes]
        if len(scopes)==1: sources[canonical_json(SourceRef(kind='manual',id=definition.id))] = manual_values[definition.id][0]
    refs = _refs(config)
    refs += [answer.overridden_source for answer in overrides.values() if answer.overridden_source]
    for ref in refs:
        if ref.kind=='count':
            sources[canonical_json(ref)] = _source(ref,'number',None,{},state='unavailable',
                message='No saved approved device classification/result dataset exists; use an explicit numeric manual input.')
            catalog[canonical_json(ref)] = {'label':f'Approved count: {ref.id} / {ref.field}','options':[],'unit':None}
    facts['dependencies'] = {canonical_json(ref):sources[canonical_json(ref)].fingerprint if canonical_json(ref) in sources else None
                             for ref in refs}
    return SavedSnapshot(inspection_id=inspection_id,config=config,stored_config_sha256=version.payload_sha256,
        panel_ids=requested,facts=facts,sources=sources,manual_values=manual_values,catalog_metadata=catalog,
        panel_choices=[{'id':p.id,'category':p.category,'filename':p.filename} for p in panels],blockers=blockers)


def source_catalog(store, inspection_id, integration_key, *, actor_id, panel_ids=()):
    """Authorized display catalog; IDs, never labels, remain the mapping keys.

    Missing-but-compatible inputs remain selectable for future data entry.
    Changed/unavailable inputs are listed with explicit diagnostics.
    """
    snapshot = capture_snapshot(store,inspection_id,integration_key,actor_id=actor_id,panel_ids=panel_ids)
    return _catalog(snapshot)


def configuration_source_catalog(store, inspection_id, version_id, *, actor_id, panel_ids=()):
    """Admin-only sample catalog for a saved draft; never final export readiness."""
    return _catalog(capture_snapshot(store,inspection_id,None,actor_id=actor_id,panel_ids=panel_ids,version_id=version_id))


def _catalog(snapshot):
    entries = [{'source':value.source.model_dump(mode='json'),'type':value.type,'state':value.state,
                'value':value.value,'fingerprint':value.fingerprint,'message':value.message,
                **snapshot.catalog_metadata.get(key,{'label':value.source.id or value.source.field or value.source.kind,'options':[],'unit':None})}
               for key,value in sorted(snapshot.sources.items())]
    return {'schema_version':1,'source_fingerprint':snapshot.fingerprint,
            'catalog_fingerprint':payload_hash({'entries':entries,'panels':snapshot.panel_choices}),
            'entries':entries,'panels':snapshot.panel_choices,'blockers':[blocker.model_dump(mode='json') for blocker in snapshot.blockers]}


def assess_readiness(store, inspection_id, integration_key, *, actor_id, panel_ids=()):
    return evaluate_snapshot(capture_snapshot(store,inspection_id,integration_key,actor_id=actor_id,panel_ids=panel_ids))


def definition_catalog(session, *, actor_id):
    """Admin picker definitions; no inspection, Points List or Event reads."""
    from alarm_inspection.integrations.pdf_repository import _actor
    _actor(session,actor_id,admin=True)
    entries=[]
    for field in ('store_number','store_type','address','city','state','inspector_name','start_date','completion_date'):
        entries.append({'source':SourceRef(kind='inspection',field=field).model_dump(mode='json'),
            'label':field.replace('_',' ').title(),'section':'Store Data',
            'type':'date' if field.endswith('_date') else 'text','options':[]})
    for task in session.scalars(select(InspectionTask).where(InspectionTask.active.is_(True)).order_by(InspectionTask.position,InspectionTask.id)):
        options=json.loads(task.options_json or '[]');validate_options(task.input_type,options)
        entry={'source':SourceRef(kind='checklist',id=task.id).model_dump(mode='json'),'label':task.text,
            'section':'Check List','type':{'checkbox':'yes_no_na','textbox':'text','dropdown':'choice'}[task.input_type],
            'options':list(CHECKBOX_CHOICES) if task.input_type=='checkbox' else options}
        entry['schema_sha256']=checklist_schema(task)
        entries.append(entry)
    return {'entries':entries,'schema_sha256':payload_hash(entries)}


def checklist_schema(task):
    # Reordering/renaming a task does not invalidate its meaning or saved answers.
    return payload_hash({'type':task.input_type,'options_json':task.options_json or '[]','active':task.active})
