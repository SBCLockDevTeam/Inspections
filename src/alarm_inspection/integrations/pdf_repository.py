"""P2 transactional primitives; semantic publication/export gates come in P3–P7.

Callers own the transaction. Nothing here registers an endpoint, resolves live
inspection answers, renders a final report, or auto-enables an integration.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import re
import secrets
from uuid import uuid4

from sqlalchemy import update

from alarm_inspection.domain.pdf_integrations import (
    ArtifactContext, FileRef, FormAnswer, IntegrationConfig, VerificationEvidence, SimpleVerificationEvidence, canonical_json, payload_hash,
)
from alarm_inspection.integrations.pdf_feature import require_available
from alarm_inspection.integrations.pdf_files import PrivatePdfFiles
from alarm_inspection.integrations.pdf_models import (
    PdfIntegration, PdfIntegrationVersion, InspectionFormDecision, PdfExportArtifact, PdfIntegrationAuditEntry,
)
from alarm_inspection.storage import Inspection, PointList, User


class ConflictError(ValueError):
    pass


def _now(): return datetime.now(timezone.utc)


def _actor(session, actor_id, *, admin=False):
    require_available(session)
    user = session.get(User, actor_id)
    if user is None or not user.is_active or user.force_password_reset or admin and not user.is_admin:
        raise PermissionError('An active authorized user is required.')
    return user


def _inspection(session, inspection_id, panel_ids=()):
    row = session.get(Inspection, inspection_id)
    if row is None or row.status == 'deleted': raise ValueError('Inspection is unavailable.')
    for ident in panel_ids:
        panel = session.get(PointList, ident)
        if panel is None or panel.inspection_id != inspection_id or panel.deleted_at is not None:
            raise ValueError('Panel scope does not belong to this active inspection.')
    return row


def _version(session, version_id):
    row = session.get(PdfIntegrationVersion, version_id, populate_existing=True)
    if row is None: raise ValueError('Unknown integration version.')
    config = IntegrationConfig.model_validate_json(row.payload_json)
    # Hash the persisted payload, not newly introduced optional model defaults.
    # Reading an older published version must never rewrite/invalidate its hash.
    if payload_hash(json.loads(row.payload_json)) != row.payload_sha256: raise ValueError('Stored configuration integrity failure.')
    if row.status == 'published':
        if json.loads(row.verification_json).get('method') == 'store_checklist_save':
            evidence = SimpleVerificationEvidence.model_validate_json(row.verification_json)
            verified = set(evidence.target_ids)
            if config.mapping_mode != 'store_checklist' or evidence.test_file.key != f'_pdf_integrations/{config.integration_key}/{row.id}/mapping-test.pdf':
                raise ValueError('Invalid simple mapping evidence.')
        else:
            evidence = VerificationEvidence.model_validate_json(row.verification_json)
            verified = {f.target_id for f in evidence.fields}
        if evidence.payload_sha256 != row.payload_sha256 or verified != {t.id for t in config.inventory.targets}:
            raise ValueError('Stored verification evidence does not match the configuration.')
    return row, config


def _active(session, version):
    integration = session.get(PdfIntegration, version.integration_key, populate_existing=True)
    if integration is None or not integration.enabled or integration.active_version_id != version.id:
        raise ValueError('Integration is disabled or this version is no longer active.')


def _audit(session, key, version_id, action, actor_id, details):
    session.add(PdfIntegrationAuditEntry(id=str(uuid4()), integration_key=key, version_id=version_id,
                                        action=action, decided_by=actor_id, decided_at=_now(),
                                        details_json=canonical_json(details)))


def create_draft(session, config: IntegrationConfig, *, files: PrivatePdfFiles, actor_id):
    _actor(session, actor_id, admin=True)
    config = IntegrationConfig.model_validate(config.model_dump())
    files.read(config.original)
    if config.normalized: files.read(config.normalized)
    if session.get(PdfIntegration, config.integration_key) is None: raise ValueError('Unknown integration.')
    row = PdfIntegrationVersion(id=config.version_id, integration_key=config.integration_key,
                                status='draft', revision=1, payload_json=canonical_json(config),
                                payload_sha256=payload_hash(config), created_by=actor_id,
                                created_at=_now(), updated_at=_now(), verification_json='{}')
    session.add(row); session.flush()
    _audit(session, config.integration_key, row.id, 'draft_created', actor_id, {'revision': 1, 'payload_sha256': row.payload_sha256})
    return row


def update_draft(session, config: IntegrationConfig, *, files: PrivatePdfFiles, expected_revision, actor_id):
    _actor(session, actor_id, admin=True)
    config = IntegrationConfig.model_validate(config.model_dump())
    previous, previous_config = _version(session, config.version_id)
    previous_json = previous.payload_json
    if config.original != previous_config.original or config.inventory != previous_config.inventory:
        raise ValueError('Template replacement/reinspection requires a new draft version.')
    files.read(config.original)
    if config.normalized: files.read(config.normalized)
    result = session.execute(update(PdfIntegrationVersion).where(
        PdfIntegrationVersion.id == config.version_id, PdfIntegrationVersion.integration_key == config.integration_key,
        PdfIntegrationVersion.status == 'draft', PdfIntegrationVersion.revision == expected_revision,
    ).values(payload_json=canonical_json(config), payload_sha256=payload_hash(config),
             revision=expected_revision + 1, verification_json='{}', updated_at=_now()))
    if result.rowcount != 1: raise ConflictError('Draft changed or has already been published.')
    _audit(session, config.integration_key, config.version_id, 'draft_updated', actor_id,
           {'revision': expected_revision + 1, 'payload_sha256': payload_hash(config),
            'previous_payload': json.loads(previous_json)})


def seal_version(session, version_id, *, files: PrivatePdfFiles, expected_revision, test_artifact_id, verified_target_ids, actor_id):
    """Freeze verified storage evidence. P4 must also enforce P3's semantic gates."""
    _actor(session, actor_id, admin=True)
    row, config = _version(session, version_id)
    files.read(config.original)
    if config.normalized: files.read(config.normalized)
    test = session.get(PdfExportArtifact, test_artifact_id)
    targets = {t.id for t in config.inventory.targets}
    if (not targets or set(verified_target_ids) != targets or len(verified_target_ids) != len(targets)
            or {m.target_id for m in config.mappings} != targets or config.applicability is None
            or config.signature_policy == 'unresolved' or config.supplemental_policy == 'unresolved'):
        raise ValueError('Configuration coverage or required policies are unresolved.')
    if (test is None or test.version_id != version_id or test.purpose != 'test' or test.status != 'ready'
            or test.config_sha256 != row.payload_sha256):
        raise ValueError('A retained test artifact for this exact configuration is required.')
    evidence = VerificationEvidence.model_validate({
        'payload_sha256': row.payload_sha256, 'test_artifact_id': test.id,
        'fields': [{'target_id': ident, 'verified_by': actor_id, 'verified_at': _now(), 'test_artifact_id': test.id}
                   for ident in sorted(targets)],
    })
    result = session.execute(update(PdfIntegrationVersion).where(
        PdfIntegrationVersion.id == version_id, PdfIntegrationVersion.status == 'draft',
        PdfIntegrationVersion.revision == expected_revision,
    ).values(status='published', revision=expected_revision + 1, verification_json=canonical_json(evidence), updated_at=_now()))
    if result.rowcount != 1: raise ConflictError('Version changed before publication.')
    _audit(session, config.integration_key, version_id, 'version_sealed', actor_id, evidence)


def activate_version(session, key, version_id, *, expected_revision, actor_id):
    _actor(session, actor_id, admin=True)
    row, config = _version(session, version_id)
    if row.integration_key != key or row.status != 'published': raise ValueError('Select a published version of this integration.')
    result = session.execute(update(PdfIntegration).where(PdfIntegration.key == key, PdfIntegration.revision == expected_revision)
                             .values(active_version_id=version_id, revision=expected_revision + 1))
    if result.rowcount != 1: raise ConflictError('Integration changed before activation.')
    _audit(session, key, version_id, 'version_activated', actor_id, {'revision': expected_revision + 1})


def set_enabled(session, key, enabled, *, expected_revision, actor_id):
    _actor(session, actor_id, admin=True)
    if type(enabled) is not bool: raise ValueError('Enablement must be Boolean.')
    row = session.get(PdfIntegration, key, populate_existing=True)
    if row is None: raise ValueError('Unknown integration.')
    if enabled:
        if not row.active_version_id: raise ValueError('A published active version is required.')
        version, _ = _version(session, row.active_version_id)
        if version.status != 'published' or version.integration_key != key: raise ValueError('Invalid active version.')
    result = session.execute(update(PdfIntegration).where(PdfIntegration.key == key, PdfIntegration.revision == expected_revision)
                             .values(enabled=enabled, revision=expected_revision + 1))
    if result.rowcount != 1: raise ConflictError('Integration changed before enablement.')
    _audit(session, key, row.active_version_id, 'enabled' if enabled else 'disabled', actor_id, {'revision': expected_revision + 1})


def decision_compatible(decision, config: IntegrationConfig):
    return any(item.id == decision.input_id and payload_hash(item) == decision.input_schema_sha256
               for item in config.manual_inputs)


def append_decision(session, version_id, inspection_id, answer: FormAnswer, *, actor_id, point_list_id=None):
    _actor(session, actor_id)
    answer = FormAnswer.model_validate(answer.model_dump())
    _inspection(session, inspection_id, [point_list_id] if point_list_id else [])
    version, config = _version(session, version_id)
    if version.status != 'published': raise ValueError('Inspection answers require a published input definition.')
    _active(session, version)
    definition = next((item for item in config.manual_inputs if item.id == answer.input_id), None)
    if definition is None: raise ValueError('Unknown manual input.')
    if (definition.scope == 'panel') != (point_list_id is not None): raise ValueError('Manual input scope mismatch.')
    definition.validate_value(answer.value)
    row = InspectionFormDecision(id=str(uuid4()), inspection_id=inspection_id, version_id=version_id,
        point_list_id=point_list_id, input_id=answer.input_id, input_schema_sha256=payload_hash(definition),
        answer_json=canonical_json(answer), decided_by=actor_id, decided_at=_now())
    session.add(row); session.flush()
    _audit(session, config.integration_key, version_id, 'form_decision', actor_id,
           {'decision_id': row.id, 'inspection_id': inspection_id, 'input_id': answer.input_id, 'override': answer.override})
    return row


def reserve_artifact(session, version_id, inspection_id, context: ArtifactContext, *, purpose, actor_id,
                     preview_id=None, confirmation_token=None, renderer_version='not-rendered-p2', filename='diagnostic.pdf'):
    _actor(session, actor_id, admin=purpose == 'test')
    if (not isinstance(filename, str) or not 1 <= len(filename) <= 255 or not filename.lower().endswith('.pdf')
            or any(ord(char) < 32 or ord(char) == 127 or char in '/\\' for char in filename)):
        raise ValueError('A safe PDF download filename is required.')
    context = ArtifactContext.model_validate(context.model_dump())
    _inspection(session, inspection_id, context.panel_ids)
    version, config = _version(session, version_id)
    if purpose not in {'test', 'preview', 'final'}: raise ValueError('Unknown artifact purpose.')
    if purpose != 'test' and version.status != 'published': raise ValueError('A published version is required.')
    if purpose != 'test': _active(session, version)
    if purpose == 'final':
        preview = verify_confirmation(session, preview_id, confirmation_token, context, actor_id=actor_id)
        if preview.version_id != version_id or preview.inspection_id != inspection_id:
            raise ValueError('Preview belongs to another inspection/version.')
    elif preview_id is not None or confirmation_token is not None:
        raise ValueError('Only finals reference a confirmed preview.')
    ident = str(uuid4()); token = secrets.token_urlsafe(32) if purpose == 'preview' else None
    row = PdfExportArtifact(id=ident, inspection_id=inspection_id, version_id=version_id,
        config_sha256=version.payload_sha256, purpose=purpose, status='pending',
        snapshot_json=canonical_json(context), file_key=PrivatePdfFiles.artifact_key(inspection_id, ident),
        renderer_version=renderer_version, download_filename=filename,
        confirmation_sha256=sha256(token.encode()).hexdigest() if token else None,
        expires_at=_now() + timedelta(minutes=30) if token else None, preview_id=preview_id,
        created_by=actor_id, created_at=_now())
    session.add(row); session.flush()
    _audit(session, config.integration_key, version_id, 'artifact_reserved', actor_id, {'artifact_id': ident, 'purpose': purpose})
    return row, token


def _artifact(session, artifact_id, actor_id):
    _actor(session, actor_id)
    row = session.get(PdfExportArtifact, artifact_id, populate_existing=True)
    if row is None: raise ValueError('Unknown artifact.')
    context = ArtifactContext.model_validate_json(row.snapshot_json)
    _inspection(session, row.inspection_id)  # Historical artifacts survive later panel removal.
    return row


def finish_artifact(session, artifact_id, receipt: FileRef, *, files: PrivatePdfFiles, actor_id):
    row = _artifact(session, artifact_id, actor_id)
    if row.created_by != actor_id or receipt.key != row.file_key: raise PermissionError('Artifact ownership/key mismatch.')
    files.read(receipt)  # Verify retained bytes before a record can become downloadable.
    result = session.execute(update(PdfExportArtifact).where(PdfExportArtifact.id == artifact_id, PdfExportArtifact.status == 'pending')
                             .values(status='ready', sha256=receipt.sha256, size=receipt.size))
    if result.rowcount != 1: raise ConflictError('Artifact is already sealed.')
    version, config = _version(session, row.version_id)
    _audit(session, config.integration_key, row.version_id, 'artifact_ready', actor_id, {'artifact_id': artifact_id, 'sha256': receipt.sha256})


def fail_artifact(session, artifact_id, error_code, *, actor_id):
    row = _artifact(session, artifact_id, actor_id)
    if row.created_by != actor_id: raise PermissionError('Artifact ownership mismatch.')
    if not re.fullmatch(r'[A-Z_]{1,80}', error_code): raise ValueError('Use a fixed, non-sensitive error code.')
    result = session.execute(update(PdfExportArtifact).where(PdfExportArtifact.id == artifact_id, PdfExportArtifact.status == 'pending')
                             .values(status='failed', error_code=error_code))
    if result.rowcount != 1: raise ConflictError('Artifact is already sealed.')
    _, config = _version(session, row.version_id)
    _audit(session, config.integration_key, row.version_id, 'artifact_failed', actor_id, {'artifact_id': artifact_id, 'error_code': error_code})


def verify_confirmation(session, artifact_id, token, context: ArtifactContext, *, actor_id):
    row = _artifact(session, artifact_id, actor_id)
    expiry = row.expires_at
    if expiry is not None and expiry.tzinfo is None: expiry = expiry.replace(tzinfo=timezone.utc)
    if (row.status != 'ready' or row.purpose != 'preview' or row.created_by != actor_id
            or expiry is None or expiry <= _now() or not isinstance(token, str)
            or not hmac.compare_digest(row.confirmation_sha256 or '', sha256(token.encode()).hexdigest())
            or row.snapshot_json != canonical_json(context)):
        raise ValueError('Preview confirmation is invalid or stale.')
    version, _ = _version(session, row.version_id)
    _active(session, version)
    _inspection(session, row.inspection_id, ArtifactContext.model_validate_json(row.snapshot_json).panel_ids)
    if version.payload_sha256 != row.config_sha256: raise ValueError('Preview configuration is stale.')
    return row


def read_artifact(session, artifact_id, *, files, actor_id):
    row = _artifact(session, artifact_id, actor_id)
    if row.status != 'ready': raise ValueError('Artifact is not ready.')
    return files.read(FileRef(key=row.file_key, sha256=row.sha256, size=row.size))
