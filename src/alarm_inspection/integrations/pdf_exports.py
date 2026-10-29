"""Snapshot-bound preview/confirmation and recoverable, immutable PDF retention."""
from datetime import date, datetime, timezone, timedelta
from hashlib import sha256
import hmac
import json
import re
import secrets
import unicodedata
from uuid import UUID, uuid4, uuid5

from pydantic import Field
from sqlalchemy import select, text, update, exists, literal
from sqlalchemy.exc import SQLAlchemyError

from alarm_inspection.domain.pdf_integrations import (ArtifactContext, Contract, Digest, RecordId, IntegrationConfig,
    FileRef, canonical_json, payload_hash)
from alarm_inspection.domain.pdf_readiness import evaluate_snapshot, issue
from alarm_inspection.integrations import pdf_repository as repo
from alarm_inspection.integrations.pdf_details import saved_scope, policy_hash
from alarm_inspection.integrations.pdf_sources import read_snapshot_session, capture_snapshot_session
from alarm_inspection.integrations.pdf_models import PdfExportArtifact, PdfIntegrationAuditEntry
from alarm_inspection.integrations.pdf_service import bounded_pdf
from alarm_inspection.storage import Inspection, User

RENDERER_VERSION='pdf-p7-1'
REQUEST_NAMESPACE=UUID('242caa58-f839-4de8-901d-8f02d3c611e4')


class PreviewRequest(Contract):
    expected_version_id: RecordId
    expected_source_fingerprint: Digest


class ConfirmationRequest(Contract):
    preview_id: RecordId
    confirmation_token: str=Field(min_length=32,max_length=128)
    preview_sha256: Digest
    request_id: RecordId
    confirmed: bool


class ExportBlocked(ValueError):
    def __init__(self,blockers):
        self.blockers=[b.model_dump(mode='json') for b in blockers]
        super().__init__('Resolve the saved-data export blockers before continuing.')


def _now():return datetime.now(timezone.utc)


def _aware(value):return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def frozen_snapshot(store,inspection_id,key,*,actor_id):
    """Scope, configuration, decisions and source rows share ONE read snapshot."""
    with read_snapshot_session(store) as session:
        scope_revision,selection=saved_scope(session,inspection_id,key) if session.info.get('pdf_integrations_available') else ('',None)
        panels=selection['panel_ids'] if selection else []
        snapshot=capture_snapshot_session(session,inspection_id,key,actor_id=actor_id,panel_ids=panels)
        config=snapshot.config
        if config and config.mapping_mode == 'store_checklist':
            scope_revision,selection = '',None
        if selection and config and selection['policy_hash']!=policy_hash(config):
            snapshot=snapshot.model_copy(update={'blockers':[*snapshot.blockers,issue('Panel scope policy changed; review and save scope again.','INVALID_SCOPE',navigation='form_details')]})
        result=evaluate_snapshot(snapshot)
        blockers=list(result.blockers)
        if config and config.filename_policy!='completion_date_panel_id':
            blockers.append(issue('An administrator must approve the download filename policy before exporting.'))
        if blockers:raise ExportBlocked(blockers)
        context=result.artifact_context()
        metadata={'renderer_version':RENDERER_VERSION,'config':config.model_dump(mode='json'),
            'config_sha256':snapshot.stored_config_sha256,'scope_revision':scope_revision,
            'facts':snapshot.facts,'captured_by':actor_id,'signature_policy':config.signature_policy,
            'deliberately_blank':[{'target_id':m.target_id,'label':m.label,'reason':m.reason} for m in config.mappings if m.disposition in {'blank','excluded','sign_later'}]}
        return context.model_copy(update={'export_metadata':metadata})


def download_filename(context):
    metadata=context.export_metadata;config=IntegrationConfig.model_validate(metadata['config']);facts=metadata['facts']['inspection']
    if config.filename_policy!='completion_date_panel_id':raise ValueError('Unapproved filename policy.')
    def clean(value,limit):
        value=unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode()
        return re.sub(r'[^A-Za-z0-9,._ -]','_',value).strip(' .')[:limit] or 'Inspection'
    stamp=date.fromisoformat(facts['completion_date'][:10]).strftime('%m-%d-%y')
    title='Fire Alarm Inspection' if config.integration_key=='nfpa72' else 'Compliance Inspection'
    panel='-Panel-'+clean(context.panel_ids[0],36) if len(context.panel_ids)==1 else ''
    return f"{clean(facts['store_number'],50)}-{clean(facts['city'],70)},{clean(facts['state'],2)}-{title}{panel}-{stamp}.pdf"


def _authorize_history(session,inspection_id,actor_id):
    user=session.get(User,actor_id)
    if user is None or not user.is_active or user.force_password_reset:raise PermissionError('Authentication required.')
    repo._inspection(session,inspection_id)
    return user


def _get(session,ident,inspection_id,key,actor_id):
    user=_authorize_history(session,inspection_id,actor_id)
    row=session.get(PdfExportArtifact,ident,populate_existing=True)
    if row is None or row.inspection_id!=inspection_id:raise ValueError('Export is unavailable for this inspection.')
    context=ArtifactContext.model_validate_json(row.snapshot_json)
    if context.export_metadata.get('config',{}).get('integration_key')!=key or row.purpose=='test':raise ValueError('Export belongs to another integration.')
    if row.purpose=='preview' and row.created_by!=actor_id:raise PermissionError('Preview belongs to another user.')
    return row,context


def _info(row):
    return {'id':row.id,'purpose':row.purpose,'status':row.status,'version_id':row.version_id,'config_sha256':row.config_sha256,
        'sha256':row.sha256,'filename':row.download_filename,'renderer_version':row.renderer_version,'created_by':row.created_by,
        'created_at':row.created_at.isoformat(),'expires_at':row.expires_at.isoformat() if row.expires_at else None,
        'error_code':row.error_code,'preview_id':row.preview_id}


def _reserve(session,ident,inspection_id,context,*,purpose,actor_id,preview=None,token=None):
    metadata=context.export_metadata;config=IntegrationConfig.model_validate(metadata['config'])
    row=PdfExportArtifact(id=ident,inspection_id=inspection_id,version_id=config.version_id,config_sha256=metadata['config_sha256'],
        purpose=purpose,status='pending',snapshot_json=canonical_json(context),file_key=f'{inspection_id}/form_exports/{ident}/document.pdf',
        renderer_version=RENDERER_VERSION,download_filename=download_filename(context),created_by=actor_id,created_at=_now(),
        preview_id=preview,confirmation_sha256=sha256(token.encode()).hexdigest() if token else None,
        expires_at=_now()+timedelta(minutes=30) if purpose=='preview' else None)
    session.add(row);session.flush()
    repo._audit(session,config.integration_key,config.version_id,'export_snapshot_accepted',actor_id,
        {'artifact_id':ident,'purpose':purpose,'source_fingerprint':context.source_fingerprint,'preview_id':preview})
    return row


def _retain(store,ident,*,files):
    with store() as session:
        row=session.get(PdfExportArtifact,ident);context=ArtifactContext.model_validate_json(row.snapshot_json)
        if row.status!='pending':return _info(row)
        config=IntegrationConfig.model_validate(context.export_metadata['config'])
        if row.renderer_version!=RENDERER_VERSION or row.config_sha256!=context.export_metadata['config_sha256']:
            raise ValueError('Pending renderer/configuration identity mismatch.')
        key,purpose,actor_id,version_id=row.file_key,row.purpose,row.created_by,row.version_id
    try:
        data=bounded_pdf(files.read(config.original),config.inventory.selected_pages,
            'export_preview' if purpose=='preview' else 'export_final',targets={'config':config.model_dump(mode='json'),'values':context.resolved_values})
        try:receipt=files.put(key,data)
        except FileExistsError:
            receipt=FileRef(key=key,sha256=sha256(data).hexdigest(),size=len(data));files.read(receipt)
    except Exception:
        with store.begin() as session:
            result=session.execute(update(PdfExportArtifact).where(PdfExportArtifact.id==ident,PdfExportArtifact.status=='pending').values(status='failed',error_code='RENDER_OR_STORAGE_FAILED'))
            if result.rowcount:repo._audit(session,config.integration_key,version_id,'export_failed',actor_id,{'artifact_id':ident,'error_code':'RENDER_OR_STORAGE_FAILED'})
        raise
    # A DB failure here deliberately leaves retained bytes + a pending record.
    # Recovery regenerates frozen bytes, verifies equality, then retries sealing.
    with store.begin() as session:
        files.read(receipt)
        result=session.execute(update(PdfExportArtifact).where(PdfExportArtifact.id==ident,PdfExportArtifact.status=='pending').values(status='ready',sha256=receipt.sha256,size=receipt.size))
        if result.rowcount:repo._audit(session,config.integration_key,version_id,'export_ready',actor_id,{'artifact_id':ident,'sha256':receipt.sha256})
        session.expire_all();return _info(session.get(PdfExportArtifact,ident))


def preview(store,inspection_id,key,request:PreviewRequest,*,files,actor_id):
    context=frozen_snapshot(store,inspection_id,key,actor_id=actor_id)
    config=context.export_metadata['config']
    if config['version_id']!=request.expected_version_id or context.source_fingerprint!=request.expected_source_fingerprint:
        raise repo.ConflictError('Saved data changed. Refresh readiness and create a new preview.')
    ident=str(uuid4());token=secrets.token_urlsafe(32)
    with store.begin() as session:_reserve(session,ident,inspection_id,context,purpose='preview',actor_id=actor_id,token=token)
    result=_retain(store,ident,files=files)
    return {**result,'confirmation_token':token,'source_fingerprint':context.source_fingerprint,'panel_ids':context.panel_ids,
            'deliberately_blank':context.export_metadata['deliberately_blank'],'signature_policy':context.export_metadata['signature_policy']}


def _check_proof(row,request,actor_id,*,expiry=True):
    if (row.purpose!='preview' or row.status!='ready' or row.created_by!=actor_id or row.sha256!=request.preview_sha256
            or row.renderer_version!=RENDERER_VERSION or not hmac.compare_digest(row.confirmation_sha256 or '',sha256(request.confirmation_token.encode()).hexdigest())
            or expiry and (row.expires_at is None or _aware(row.expires_at)<=_now())):
        raise repo.ConflictError('Preview proof expired or changed. Create and review a new preview.')


def confirm(store,inspection_id,key,request:ConfirmationRequest,*,files,actor_id):
    if request.confirmed is not True:raise ValueError('Explicit preview confirmation is required.')
    ident=str(uuid5(REQUEST_NAMESPACE,canonical_json([inspection_id,actor_id,request.request_id])))
    with store.begin() as session:
        if session.get_bind().dialect.name=='sqlite':session.execute(text('BEGIN IMMEDIATE'))
        _authorize_history(session,inspection_id,actor_id)
        session.execute(select(Inspection).where(Inspection.id==inspection_id).with_for_update()).scalar_one()
        previous,old=_get(session,request.preview_id,inspection_id,key,actor_id)
        existing=session.get(PdfExportArtifact,ident)
        if existing:
            _check_proof(previous,request,actor_id,expiry=False)
            if existing.purpose!='final' or existing.preview_id!=previous.id:raise repo.ConflictError('Request ID already belongs to another confirmation.')
            if existing.status=='ready':files.read(FileRef(key=existing.file_key,sha256=existing.sha256,size=existing.size))
            return _info(existing)
        _check_proof(previous,request,actor_id)
        files.read(FileRef(key=previous.file_key,sha256=previous.sha256,size=previous.size))
        current=frozen_snapshot(store,inspection_id,key,actor_id=actor_id)
        if canonical_json(old)!=canonical_json(current):raise repo.ConflictError('Inspection data, scope or configuration changed since preview. Create a new preview.')
        _reserve(session,ident,inspection_id,current,purpose='final',actor_id=actor_id,preview=previous.id)
    return _retain(store,ident,files=files)


def history(store,inspection_id,key,*,actor_id):
    with store() as session:
        _authorize_history(session,inspection_id,actor_id)
        rows=session.scalars(select(PdfExportArtifact).where(PdfExportArtifact.inspection_id==inspection_id,PdfExportArtifact.purpose=='final').order_by(PdfExportArtifact.created_at.desc()))
        return {'exports':[_info(row) for row in rows if ArtifactContext.model_validate_json(row.snapshot_json).export_metadata.get('config',{}).get('integration_key')==key]}


def download(store,inspection_id,key,ident,*,files,actor_id):
    with store() as session:
        row,context=_get(session,ident,inspection_id,key,actor_id)
        if row.status!='ready':raise ValueError('Export is not ready for download.')
        if row.purpose=='preview' and _aware(row.expires_at)<=_now():raise repo.ConflictError('Preview expired; create a new one.')
        return files.read(FileRef(key=row.file_key,sha256=row.sha256,size=row.size)),_info(row)


def provenance(store,inspection_id,key,ident,*,actor_id):
    with store() as session:
        row,context=_get(session,ident,inspection_id,key,actor_id)
        public=context.model_dump(mode='json')
        def redact(value):
            if isinstance(value,dict):return {key:redact(item) for key,item in value.items() if key not in {'path','file_key'}}
            if isinstance(value,list):return [redact(item) for item in value]
            return value
        public=redact(public)
        for name in ('original','normalized'):
            receipt=public['export_metadata']['config'].get(name)
            if receipt:receipt.pop('key',None)
        return {'artifact':_info(row),'snapshot':public}


def recover(store,inspection_id,key,ident,*,files,actor_id):
    with store() as session:
        row,context=_get(session,ident,inspection_id,key,actor_id)
        if row.created_by!=actor_id and not session.get(User,actor_id).is_admin:raise PermissionError('Recovery requires the requester or an administrator.')
        if row.status!='pending':return _info(row)
        if _aware(row.created_at)>_now()-timedelta(minutes=2):raise repo.ConflictError('Export is still processing. Retry recovery after two minutes.')
    return _retain(store,ident,files=files)


def cleanup_expired_previews(store,*,files,actor_id,limit=100):
    """Bounded explicit maintenance; never removes originals or final artifacts."""
    if type(limit) is not int or not 1<=limit<=100:raise ValueError('Cleanup limit must be 1–100.')
    removed=[]
    with store.begin() as session:
        repo._actor(session,actor_id,admin=True)
        rows=list(session.scalars(select(PdfExportArtifact).where(PdfExportArtifact.purpose=='preview',
            PdfExportArtifact.status=='ready',PdfExportArtifact.expires_at<_now()-timedelta(days=1),
            ~exists(select(PdfIntegrationAuditEntry.id).where(PdfIntegrationAuditEntry.action=='expired_preview_cleanup',
                PdfIntegrationAuditEntry.details_json==(literal('{"artifact_id":"')+PdfExportArtifact.id+literal('"}'))))).order_by(PdfExportArtifact.expires_at).limit(limit)))
        for row in rows:
            if row.renderer_version!=RENDERER_VERSION:continue
            files._path(row.file_key).unlink(missing_ok=True)
            context=ArtifactContext.model_validate_json(row.snapshot_json)
            repo._audit(session,context.export_metadata['config']['integration_key'],row.version_id,'expired_preview_cleanup',actor_id,{'artifact_id':row.id})
            removed.append(row.id)
    return {'expired_preview_ids':removed}
