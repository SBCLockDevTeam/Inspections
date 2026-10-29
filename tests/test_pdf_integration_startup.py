"""Disabled/unavailable integrations must not interfere with legacy startup."""
import os
import sqlite3
import subprocess
import sys

from sqlalchemy import inspect, select, text

from test_pdf_integration_baseline import populated_baseline
from alarm_inspection.storage import Base, open_store


def _legacy_rows(engine):
    with engine.connect() as connection:
        return {table.name: list(connection.execute(select(table).order_by(*table.primary_key.columns)))
                for table in Base.metadata.sorted_tables}


def test_populated_database_enable_restart_disable_preserves_all_legacy_records(populated_baseline, monkeypatch):
    _, source = populated_baseline
    old = open_store(); before = _legacy_rows(old.kw['bind']); original = source.read_bytes()
    monkeypatch.setenv('INSPECTIONS_PDF_INTEGRATIONS_ENABLED', 'true')
    for _ in range(2):
        store = open_store()
        with store() as session: assert session.info['pdf_integrations_available'] is True
        assert _legacy_rows(store.kw['bind']) == before
        store.kw['bind'].dispose()
    monkeypatch.setenv('INSPECTIONS_PDF_INTEGRATIONS_ENABLED', 'false')
    store = open_store()
    assert _legacy_rows(store.kw['bind']) == before and source.read_bytes() == original
    with store() as session: assert session.info['pdf_integrations_available'] is False
    store.kw['bind'].dispose(); old.kw['bind'].dispose()


def test_default_disabled_does_not_import_new_models_or_initialize_tables(tmp_path):
    environment = dict(os.environ, DATABASE_URL=f'sqlite:///{tmp_path / "disabled.db"}')
    environment.pop('INSPECTIONS_PDF_INTEGRATIONS_ENABLED', None)
    code = ('import sys; from alarm_inspection.storage import open_store; from sqlalchemy import inspect; '
            's=open_store(); assert "alarm_inspection.integrations.pdf_models" not in sys.modules; '
            'assert "pdf_integrations" not in inspect(s.kw["bind"]).get_table_names()')
    subprocess.run([sys.executable, '-c', code], env=environment, check=True, timeout=15)


def test_optional_initialization_failure_keeps_legacy_application_working(tmp_path, monkeypatch, caplog):
    from fastapi.testclient import TestClient
    from alarm_inspection.integrations import pdf_schema
    from alarm_inspection.api.app import create_app
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "failure.db"}')
    monkeypatch.setenv('INSPECTIONS_PDF_INTEGRATIONS_ENABLED', 'true')
    def fail(_): raise RuntimeError('PRIVATE_FAILURE_MARKER')
    monkeypatch.setattr(pdf_schema, 'initialize_pdf_store', fail)
    app = create_app()
    with TestClient(app) as client: assert client.get('/health').json() == {'status':'ok'}
    store = open_store()
    with store() as session: assert session.info['pdf_integrations_available'] is False
    assert 'PRIVATE_FAILURE_MARKER' not in caplog.text
    assert 'existing inspection workflows remain enabled' in caplog.text


def test_unknown_schema_version_fails_closed_without_deleting_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "future.db"}')
    monkeypatch.setenv('INSPECTIONS_PDF_INTEGRATIONS_ENABLED', 'true')
    store = open_store()
    with store.kw['bind'].begin() as connection:
        connection.execute(text('UPDATE pdf_integration_schema SET version = 2'))
    restarted = open_store()
    with restarted() as session: assert session.info['pdf_integrations_available'] is False
    with restarted.kw['bind'].connect() as connection:
        assert connection.execute(text('SELECT version FROM pdf_integration_schema')).scalar_one() == 2
        assert connection.execute(text('SELECT COUNT(*) FROM pdf_integrations')).scalar_one() == 2
