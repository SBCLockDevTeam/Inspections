"""Same lifecycle checks against isolated SQLite and PostgreSQL schemas."""
from datetime import date, datetime, timezone
import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from pdf_storage_fixtures import config_data, template_bytes
from alarm_inspection.domain.pdf_integrations import ArtifactContext, FormAnswer, IntegrationConfig, payload_hash
from alarm_inspection.integrations.pdf_files import PrivatePdfFiles
from alarm_inspection.integrations.pdf_models import PdfIntegration, PdfIntegrationVersion, InspectionFormDecision, PdfExportArtifact, PdfIntegrationAuditEntry
from alarm_inspection.integrations.pdf_repository import (
    create_draft, update_draft, seal_version, activate_version, set_enabled, append_decision,
    reserve_artifact, finish_artifact, fail_artifact, verify_confirmation, read_artifact, ConflictError,
)
from alarm_inspection.storage import (
    Base, Inspection, InspectionAuditEntry, InspectionPdfDraft, InspectionPdfTemplateDraft,
    InspectionTask, InspectionChecklistDecision, PointList, PointListDecision, PointListEventDate,
    PointListPendingEventDate, SourceFile, User, open_store,
)


@pytest.fixture(params=['sqlite', 'postgres'])
def database(request, tmp_path, monkeypatch):
    schema = None; admin_engine = None
    if request.param == 'postgres':
        url = os.getenv('INSPECTIONS_PDF_TEST_POSTGRES_URL')
        if not url: pytest.skip('Set a disposable PostgreSQL test URL for cross-database verification')
        admin_engine = create_engine(url)
        schema = 'pdf_test_' + uuid4().hex
        with admin_engine.begin() as connection: connection.exec_driver_sql(f'CREATE SCHEMA {schema}')
        url = make_url(url).update_query_dict({'options': f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    else: url = f'sqlite:///{tmp_path / "pdf.db"}'
    monkeypatch.setenv('DATABASE_URL', url)
    monkeypatch.delenv('INSPECTIONS_PDF_INTEGRATIONS_ENABLED', raising=False)
    legacy = open_store()
    now = datetime.now(timezone.utc)
    inspection_id = str(uuid4())
    with legacy.begin() as session:
        session.add(User(id='admin', email='admin@example.invalid', password_hash='synthetic', is_admin=True,
                         force_password_reset=False, created_at=now))
        session.add(User(id='tech', email='tech@example.invalid', password_hash='synthetic', is_admin=False,
                         force_password_reset=False, created_at=now))
        session.add(Inspection(id=inspection_id, store_number='SYNTHETIC', address='1 Example', city='Example',
                               state='VA', start_date=date(2026,10,1), completion_date=date(2026,10,2), created_at=now))
        session.add(PointList(id='panel', inspection_id=inspection_id, category='Fire', filename='synthetic.xlsx',
                              path=str(tmp_path / 'synthetic.xlsx'), accepted_at=now))
        for address in (1, 2):
            session.add(PointListDecision(id=f'point-{address}', inspection_id=inspection_id, point_list_id='panel',
                                          address=address, text='Synthetic device', location='Example', accepted=address == 1))
        session.add(PointListEventDate(id='accepted', inspection_id=inspection_id, point_list_id='panel',
                                       point_address=1, event_timestamp=now, source_filename='first.xlsx'))
        session.add(PointListPendingEventDate(inspection_id=inspection_id, point_list_id='panel',
                                              point_address=2, event_timestamp=now, source_filename='second.xlsx'))
        session.add(InspectionPdfDraft(inspection_id=inspection_id, fields_json='{"legacy":"retained"}', updated_at=now))
        session.add(InspectionPdfTemplateDraft(inspection_id=inspection_id, template_key='nfpa72',
                                               fields_json='{"legacy":"retained"}', updated_at=now))
        session.add(InspectionTask(id='task', text='Synthetic task', text_key='synthetic task', created_at=now))
        session.add(InspectionChecklistDecision(id='answer', inspection_id=inspection_id, task_id='task',
                                                 task_text='Synthetic task', value='No', completed=True,
                                                 decided_by='tech', decided_at=now))
        session.add(InspectionAuditEntry(id='legacy-audit', inspection_id=inspection_id, point_list_id='panel',
                                         action='synthetic', details_json='{"previous":"retained"}',
                                         decided_by='tech', decided_at=now))
    monkeypatch.setenv('INSPECTIONS_PDF_INTEGRATIONS_ENABLED', 'true')
    store = open_store()
    files = PrivatePdfFiles(tmp_path / 'private')
    try: yield store, files, inspection_id, legacy
    finally:
        store.kw['bind'].dispose(); legacy.kw['bind'].dispose()
        if admin_engine:
            with admin_engine.begin() as connection: connection.exec_driver_sql(f'DROP SCHEMA {schema} CASCADE')
            admin_engine.dispose()


def draft(store, files):
    config = IntegrationConfig.model_validate(config_data())
    files.put(config.original.key, template_bytes())
    with store.begin() as session: create_draft(session, config, files=files, actor_id='admin')
    return config


def published(store, files, inspection_id):
    config = draft(store, files)
    context = ArtifactContext(source_fingerprint=payload_hash(config))
    with store.begin() as session:
        row, _ = reserve_artifact(session, config.version_id, inspection_id, context, purpose='test', actor_id='admin')
        receipt = files.put(row.file_key, b'SYNTHETIC TEST PDF')
        finish_artifact(session, row.id, receipt, files=files, actor_id='admin')
        seal_version(session, config.version_id, files=files, expected_revision=1, test_artifact_id=row.id,
                     verified_target_ids=[t.id for t in config.inventory.targets], actor_id='admin')
        activate_version(session, 'compliance', config.version_id, expected_revision=1, actor_id='admin')
    return config


def test_additive_idempotent_initialization_preserves_legacy(database):
    store, _, ident, legacy = database
    def legacy_rows(engine):
        from sqlalchemy import select
        with engine.connect() as connection:
            return {table.name: list(connection.execute(select(table).order_by(*table.primary_key.columns)))
                    for table in Base.metadata.sorted_tables}
    before = legacy_rows(legacy.kw['bind'])
    assert set(inspect(store.kw['bind']).get_table_names()) >= set(Base.metadata.tables)
    for _ in range(2):
        another = open_store()
        with another() as session:
            assert session.query(PdfIntegration).count() == 2
            assert session.query(PdfIntegrationVersion).count() == 0
            assert not any(i.enabled or i.active_version_id for i in session.query(PdfIntegration))
            assert session.get(Inspection, ident).store_number == 'SYNTHETIC'
            assert session.query(User).count() == 2
        another.kw['bind'].dispose()
        assert legacy_rows(store.kw['bind']) == before


def test_stale_draft_update_and_published_immutability(database):
    store, files, ident, _ = database
    config = draft(store, files)
    with store.begin() as session: update_draft(session, config, files=files, expected_revision=1, actor_id='admin')
    with pytest.raises(ConflictError), store.begin() as session:
        update_draft(session, config, files=files, expected_revision=1, actor_id='admin')
    config = published(store, files, ident)
    with pytest.raises(ConflictError), store.begin() as session:
        update_draft(session, config, files=files, expected_revision=2, actor_id='admin')
    with pytest.raises(DBAPIError), store.begin() as session:
        session.execute(text('UPDATE pdf_integration_versions SET payload_json = :value WHERE id = :id'),
                        {'value':'{}','id':config.version_id})


def test_append_only_answers_audit_and_deleted_actor_retention(database):
    store, files, ident, _ = database
    config = published(store, files, ident)
    with store.begin() as session:
        set_enabled(session, 'compliance', True, expected_revision=2, actor_id='admin')
        first = append_decision(session, config.version_id, ident, FormAnswer(input_id='remarks', value='First'), actor_id='tech')
        append_decision(session, config.version_id, ident, FormAnswer(input_id='remarks', value='Second'), actor_id='tech')
        decision_id = first.id
    with pytest.raises(DBAPIError), store.begin() as session:
        session.execute(text('DELETE FROM inspection_form_decisions WHERE id = :id'), {'id':decision_id})
    with pytest.raises(DBAPIError), store.begin() as session:
        session.execute(text('UPDATE pdf_integration_audit_entries SET action = :value'), {'value':'changed'})
    with store.begin() as session: session.delete(session.get(User, 'tech'))
    with store() as session:
        assert session.query(InspectionFormDecision).count() == 2
        assert session.get(InspectionFormDecision, decision_id).decided_by == 'tech'


def test_preview_confirmation_retention_and_failure_states(database):
    store, files, ident, _ = database
    config = published(store, files, ident)
    context = ArtifactContext(source_fingerprint='b' * 64)
    with store.begin() as session:
        set_enabled(session, 'compliance', True, expected_revision=2, actor_id='admin')
        row, token = reserve_artifact(session, config.version_id, ident, context, purpose='preview', actor_id='tech')
        artifact_id = row.id
        with pytest.raises(ValueError): read_artifact(session, artifact_id, files=files, actor_id='tech')
        receipt = files.put(row.file_key, b'SYNTHETIC PREVIEW PDF')
        finish_artifact(session, artifact_id, receipt, files=files, actor_id='tech')
        assert verify_confirmation(session, artifact_id, token, context, actor_id='tech')
        with pytest.raises(ValueError): verify_confirmation(session, artifact_id, 'forged', context, actor_id='tech')
        with pytest.raises(ValueError): verify_confirmation(session, artifact_id, token, ArtifactContext(source_fingerprint='c'*64), actor_id='tech')
        assert read_artifact(session, artifact_id, files=files, actor_id='tech') == b'SYNTHETIC PREVIEW PDF'
    with pytest.raises(DBAPIError), store.begin() as session:
        session.execute(text('UPDATE pdf_export_artifacts SET snapshot_json = :v WHERE id = :id'), {'v':'{}','id':artifact_id})
    with store.begin() as session:
        row, _ = reserve_artifact(session, config.version_id, ident, context, purpose='preview', actor_id='tech')
        fail_artifact(session, row.id, 'RENDER_FAILED', actor_id='tech')
        with pytest.raises(ValueError): read_artifact(session, row.id, files=files, actor_id='tech')


def test_permissions_scope_references_and_disable_gate(database, monkeypatch):
    store, files, ident, _ = database
    config = draft(store, files)
    with pytest.raises(PermissionError), store.begin() as session:
        update_draft(session, config, files=files, expected_revision=1, actor_id='tech')
    with pytest.raises(ValueError), store.begin() as session:
        activate_version(session, 'compliance', config.version_id, expected_revision=1, actor_id='admin')
    with pytest.raises(ValueError), store.begin() as session:
        reserve_artifact(session, config.version_id, ident, ArtifactContext(source_fingerprint='a'*64, panel_ids=['wrong']), purpose='test', actor_id='admin')
    with pytest.raises(DBAPIError), store.begin() as session:
        session.add(PdfIntegrationVersion(id=str(uuid4()), integration_key='missing', payload_json='{}', payload_sha256='a'*64,
                                         created_by='admin', created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
    monkeypatch.setenv('INSPECTIONS_PDF_INTEGRATIONS_ENABLED', 'false')
    with pytest.raises(RuntimeError), store.begin() as session:
        create_draft(session, IntegrationConfig.model_validate(config_data()), files=files, actor_id='admin')


def test_activation_revision_guards_and_per_integration_enablement(database):
    store, files, ident, _ = database
    config = published(store, files, ident)
    with store.begin() as session: set_enabled(session, 'compliance', True, expected_revision=2, actor_id='admin')
    with pytest.raises(ConflictError), store.begin() as session:
        set_enabled(session, 'compliance', False, expected_revision=2, actor_id='admin')
    with store() as session:
        row = session.get(PdfIntegration, 'compliance')
        assert row.enabled is True and row.active_version_id == config.version_id


def test_pending_file_survives_transaction_failure_and_can_be_finalized(database):
    store, files, ident, _ = database
    config = published(store, files, ident)
    with store.begin() as session:
        set_enabled(session, 'compliance', True, expected_revision=2, actor_id='admin')
        row, _ = reserve_artifact(session, config.version_id, ident, ArtifactContext(source_fingerprint='d'*64),
                                  purpose='preview', actor_id='tech')
        artifact_id, key = row.id, row.file_key
    receipt = files.put(key, b'SYNTHETIC RETAINED OUTPUT')
    with pytest.raises(RuntimeError), store.begin() as session:
        finish_artifact(session, artifact_id, receipt, files=files, actor_id='tech')
        raise RuntimeError('Simulated transaction/commit failure')
    with store() as session:
        assert session.get(PdfExportArtifact, artifact_id).status == 'pending'
        with pytest.raises(ValueError): read_artifact(session, artifact_id, files=files, actor_id='tech')
    with store.begin() as session: finish_artifact(session, artifact_id, receipt, files=files, actor_id='tech')
    restarted = open_store()
    try:
        with restarted() as session:
            assert read_artifact(session, artifact_id, files=files, actor_id='tech') == b'SYNTHETIC RETAINED OUTPUT'
            assert session.get(PdfIntegrationVersion, config.version_id).status == 'published'
            assert session.get(PdfIntegration, 'compliance').enabled is True
    finally: restarted.kw['bind'].dispose()


def test_two_sessions_reject_stale_revision_and_preserve_prior_payload(database):
    store, files, _, _ = database
    config = draft(store, files)
    with store() as first, store() as second:
        assert first.get(PdfIntegrationVersion, config.version_id).revision == 1
        assert second.get(PdfIntegrationVersion, config.version_id).revision == 1
        update_draft(first, config, files=files, expected_revision=1, actor_id='admin'); first.commit()
        with pytest.raises(ConflictError): update_draft(second, config, files=files, expected_revision=1, actor_id='admin')
        second.rollback()
    with store() as session:
        audit = session.query(PdfIntegrationAuditEntry).filter_by(action='draft_updated').one()
        assert json.loads(audit.details_json)['previous_payload']['version_id'] == config.version_id


def test_history_read_survives_panel_deletion_but_confirmation_rejects_it(database):
    store, files, ident, _ = database
    config = published(store, files, ident)
    context = ArtifactContext(source_fingerprint='f'*64, panel_ids=['panel'])
    with store.begin() as session:
        set_enabled(session, 'compliance', True, expected_revision=2, actor_id='admin')
        row, token = reserve_artifact(session, config.version_id, ident, context, purpose='preview', actor_id='tech')
        finish_artifact(session, row.id, files.put(row.file_key, b'SYNTHETIC ARCHIVE'), files=files, actor_id='tech')
        artifact_id = row.id
    with store.begin() as session: session.get(PointList, 'panel').deleted_at = datetime.now(timezone.utc)
    with store() as session:
        assert read_artifact(session, artifact_id, files=files, actor_id='tech') == b'SYNTHETIC ARCHIVE'
        with pytest.raises(ValueError): verify_confirmation(session, artifact_id, token, context, actor_id='tech')


def test_unknown_metadata_version_disables_new_feature_only(database):
    store, _, ident, _ = database
    with store.kw['bind'].begin() as connection: connection.exec_driver_sql('UPDATE pdf_integration_schema SET version = 2')
    restarted = open_store()
    try:
        with restarted() as session:
            assert not session.info['pdf_integrations_available']
            assert session.get(Inspection, ident).store_number == 'SYNTHETIC'
    finally: restarted.kw['bind'].dispose()


def test_disabled_integration_prevents_new_previews_and_input_semantics_control_reuse(database):
    from alarm_inspection.integrations.pdf_repository import decision_compatible
    store, files, ident, _ = database
    config = published(store, files, ident)
    context = ArtifactContext(source_fingerprint='e'*64)
    with store.begin() as session:
        with pytest.raises(ValueError): reserve_artifact(session, config.version_id, ident, context, purpose='preview', actor_id='tech')
        set_enabled(session, 'compliance', True, expected_revision=2, actor_id='admin')
        answer = append_decision(session, config.version_id, ident, FormAnswer(input_id='remarks', value='Retained'), actor_id='tech')
        assert decision_compatible(answer, config)
        modified = json.loads(config.model_dump_json()); modified['manual_inputs'][0]['meaning'] = 'A different question'
        assert not decision_compatible(answer, IntegrationConfig.model_validate(modified))
        with pytest.raises(ValueError): reserve_artifact(session, config.version_id, ident, context, purpose='preview', actor_id='tech', filename='../escape.pdf')


def test_missing_template_cannot_create_draft(database):
    store, files, _, _ = database
    with pytest.raises(FileNotFoundError), store.begin() as session:
        create_draft(session, IntegrationConfig.model_validate(config_data()), files=files, actor_id='admin')
    with store() as session: assert session.query(PdfIntegrationVersion).count() == 0


def test_task_default_additive_migration_preserves_definitions_and_decisions(database):
    store, _, _, _ = database
    engine = store.kw['bind']
    def retained():
        with engine.connect() as connection:
            tasks = list(connection.execute(text('SELECT id,text,text_key,input_type,options_json,section,position,active,created_at FROM inspection_tasks ORDER BY id')))
            decisions = list(connection.execute(text('SELECT * FROM inspection_checklist_decisions ORDER BY id')))
            return tasks, decisions
    before = retained()
    with engine.begin() as connection: connection.execute(text('ALTER TABLE inspection_tasks DROP COLUMN default_value'))
    for _ in range(2):
        reopened = open_store()
        try:
            with reopened() as session: assert session.get(InspectionTask, 'task').default_value == ''
            assert retained() == before
        finally: reopened.kw['bind'].dispose()


@pytest.mark.parametrize('section', ['nfpa72', 'store_data'])
def test_section_reorders_reject_concurrent_stale_order(database, section):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi.testclient import TestClient
    from fastapi import FastAPI, Request
    from alarm_inspection.api.routers.inspection_tasks import create_admin_router
    store, _, _, _ = database
    now = datetime.now(timezone.utc)
    with store.begin() as session:
        for ident in ('order-a', 'order-b'):
            session.add(InspectionTask(id=ident, text=ident, text_key=ident, section=section, position=1 if ident=='order-a' else 2, created_at=now))
    app = FastAPI()
    @app.middleware('http')
    async def auth(request: Request, call_next):
        with store() as session: request.state.current_user = session.get(User, 'admin')
        return await call_next(request)
    app.include_router(create_admin_router(store))
    client = TestClient(app)
    from alarm_inspection.inspection_fields import native_fields
    with store() as session: builtins = [field['id'] for field in native_fields(session)] if section=='store_data' else []
    expected = builtins + ['order-a','order-b']
    payload = {'section':section,'expected_order':expected,'task_ids':list(reversed(expected))}
    if store.kw['bind'].dialect.name == 'postgresql':
        barrier = Barrier(2)
        def reorder(_):
            barrier.wait(timeout=10)
            return client.put('/api/admin/inspection-tasks/order', json=payload).status_code
        with ThreadPoolExecutor(max_workers=2) as pool: statuses = list(pool.map(reorder, range(2)))
    else:
        statuses = [client.put('/api/admin/inspection-tasks/order', json=payload).status_code for _ in range(2)]
    assert sorted(statuses) == [200, 409]
