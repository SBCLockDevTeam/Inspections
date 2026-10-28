"""Disposable data baseline for later additive integration migrations.

No application database, customer file, or production backup is used here.
"""
from datetime import date, datetime, timezone
import json
import sqlite3

import pytest

pytest.importorskip('sqlalchemy')

from alarm_inspection.storage import (
    Inspection, InspectionAuditEntry, InspectionChecklistDecision, InspectionPdfDraft,
    InspectionPdfTemplateDraft, InspectionTask, PointList, PointListDecision,
    PointListEventDate, PointListPendingEventDate, SourceFile, User, open_store,
)


@pytest.fixture
def populated_baseline(tmp_path, monkeypatch):
    path = tmp_path / 'baseline.db'
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{path}')
    store = open_store()
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    with store.begin() as session:
        session.add(User(id='technician', email='synthetic@example.invalid', password_hash='not-a-real-hash',
                         is_admin=False, force_password_reset=False, is_active=True, created_at=now))
        for ident, status in [('active', 'pending_event_history'), ('deleted', 'deleted')]:
            session.add(Inspection(id=ident, store_number='SYNTHETIC', store_type='Test Store',
                                   address='1 Synthetic Street', city='Example', state='VA',
                                   inspector_name='Test Technician', start_date=date(2026, 10, 1),
                                   completion_date=date(2026, 10, 2), status=status, created_at=now))
        for ident, category in [('fire', 'Fire'), ('combo', 'Combo')]:
            session.add(PointList(id=ident, inspection_id='active', category=category,
                                  filename=f'{ident}.xlsx', path=str(tmp_path / f'{ident}.xlsx'), accepted_at=now))
        for ident, panel, address, accepted in [('accepted', 'fire', 1, True),
                                               ('review', 'fire', 2, False), ('combo-point', 'combo', 1, True)]:
            session.add(PointListDecision(id=ident, inspection_id='active', point_list_id=panel,
                                          address=address, text='Synthetic device', location='Test location',
                                          accepted=accepted, deleted=False, reason='Synthetic baseline'))
        session.add(PointListEventDate(id='accepted-time', inspection_id='active', point_list_id='fire',
                                       point_address=1, event_timestamp=now, source_filename='first-history.xlsx'))
        session.add(PointListPendingEventDate(inspection_id='active', point_list_id='combo',
                                              point_address=1, event_timestamp=now, source_filename='later-history.xlsx'))
        for index, (kind, value, completed, options, active) in enumerate([
            ('checkbox', '', True, [], True),  # Legacy Yes; never rewrite the row.
            ('checkbox', '', False, [], True),  # Legacy unanswered.
            ('checkbox', 'No', True, ['Yes', 'No', 'NA'], True),
            ('textbox', 'Synthetic reading', True, [], False),
            ('dropdown', 'Removed option', True, ['Current option'], True),
        ]):
            task_id = f'task-{index}'
            session.add(InspectionTask(id=task_id, text=f'Synthetic task {index}', text_key=f'synthetic task {index}',
                                       input_type=kind, options_json=json.dumps(options), position=index + 1,
                                       active=active, created_at=now))
            session.add(InspectionChecklistDecision(id=f'answer-{index}', inspection_id='active', task_id=task_id,
                                                     task_text=f'Synthetic task {index}', input_type=kind,
                                                     options_json=json.dumps(['Removed option'] if kind == 'dropdown' else options),
                                                     value=value, completed=completed, decided_by='technician', decided_at=now))
        session.add(InspectionPdfDraft(inspection_id='active', fields_json='{"property_name":"Legacy draft"}', updated_at=now))
        session.add(InspectionPdfTemplateDraft(inspection_id='active', template_key='nfpa72',
                                               fields_json='{"Legacy field":"Retained"}', updated_at=now))
        session.add(InspectionAuditEntry(id='audit', inspection_id='active', point_list_id='fire',
                                         action='synthetic_baseline', details_json='{"previous":"retained"}',
                                         decided_by='technician', decided_at=now))
        source = tmp_path / 'source.xlsx'
        source.write_bytes(b'SYNTHETIC ORIGINAL UPLOAD')
        session.add(SourceFile(id='source', inspection_id='active', filename='source.xlsx', path=str(source), kind='points_list'))
    return path, source


def _snapshot(path):
    with sqlite3.connect(path) as connection:
        return tuple(connection.iterdump())


def test_reinitialization_and_disposable_backup_restore_preserve_baseline(populated_baseline, tmp_path):
    path, source = populated_baseline
    before = _snapshot(path)
    original_upload = source.read_bytes()
    open_store()
    open_store()
    assert _snapshot(path) == before
    backup = tmp_path / 'backup.db'
    with sqlite3.connect(path) as database, sqlite3.connect(backup) as saved:
        database.backup(saved)
    upload_backup = tmp_path / 'backup-upload.xlsx'
    upload_backup.write_bytes(original_upload)
    # Rehearse an independent restoration, without destroying the working fixture.
    restored = tmp_path / 'restored.db'
    with sqlite3.connect(backup) as saved, sqlite3.connect(restored) as database:
        saved.backup(database)
    assert _snapshot(restored) == before
    assert upload_backup.read_bytes() == original_upload == source.read_bytes()
