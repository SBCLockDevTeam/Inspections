"""Transactional, versioned, additive initialization for both supported databases."""
from sqlalchemy import event, inspect, select

from alarm_inspection.integrations.pdf_models import PdfBase, PdfIntegration, PdfSchemaState


def _sqlite_foreign_keys(connection, _):
    cursor = connection.cursor()
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.close()


def _guard(connection, table, condition):
    """Reject DELETE and guarded UPDATE, including bulk/direct SQL writes."""
    name = table + '_immutable'
    if connection.dialect.name == 'sqlite':
        for operation, when in [('DELETE', ''), ('UPDATE', ' WHEN ' + condition)]:
            connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS {name}_{operation.lower()} "
                f"BEFORE {operation} ON {table}{when} BEGIN SELECT RAISE(ABORT, 'PDF immutable record'); END")
    else:
        connection.exec_driver_sql(f"CREATE OR REPLACE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ "
            f"BEGIN IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'PDF immutable record'; END IF; "
            f"IF {condition} THEN RAISE EXCEPTION 'PDF immutable record'; END IF; RETURN NEW; END $$")
        connection.exec_driver_sql(f'DROP TRIGGER IF EXISTS {name} ON {table}')
        connection.exec_driver_sql(f'CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {table} '
                                  f'FOR EACH ROW EXECUTE FUNCTION {name}()')


def initialize_pdf_store(engine):
    if engine.dialect.name not in {'sqlite', 'postgresql'}:
        raise RuntimeError('Unsupported PDF integration database.')
    if engine.dialect.name == 'sqlite' and not event.contains(engine, 'connect', _sqlite_foreign_keys):
        event.listen(engine, 'connect', _sqlite_foreign_keys)
    with engine.begin() as connection:
        if connection.dialect.name == 'sqlite':
            connection.exec_driver_sql('PRAGMA foreign_keys=ON')
            connection.exec_driver_sql('BEGIN IMMEDIATE')
        else:
            connection.exec_driver_sql('SELECT pg_advisory_xact_lock(78234192001)')
        existing = set(inspect(connection).get_table_names())
        if 'pdf_integration_schema' not in existing and existing.intersection(PdfBase.metadata.tables):
            raise RuntimeError('Unversioned partial PDF integration schema requires explicit repair.')
        if 'pdf_integration_schema' in existing:
            version = connection.execute(select(PdfSchemaState.version)).scalar_one_or_none()
            if version != 1: raise RuntimeError('Unsupported PDF integration schema; explicit migration required.')
        PdfBase.metadata.create_all(connection)
        if connection.execute(select(PdfSchemaState.id)).first() is None:
            connection.execute(PdfSchemaState.__table__.insert().values(id=1, version=1))
        keys = set(connection.execute(select(PdfIntegration.key)).scalars())
        for key in ('nfpa72', 'compliance'):
            if key not in keys:
                connection.execute(PdfIntegration.__table__.insert().values(key=key, enabled=False, revision=1))
        _guard(connection, 'inspection_form_decisions', '1 = 1')
        _guard(connection, 'pdf_integration_audit_entries', '1 = 1')
        _guard(connection, 'pdf_integration_versions', "OLD.status = 'published' OR NEW.id <> OLD.id "
               "OR NEW.integration_key <> OLD.integration_key OR NEW.revision <> OLD.revision + 1")
        frozen = ('id', 'inspection_id', 'version_id', 'config_sha256', 'purpose', 'snapshot_json', 'file_key',
                  'renderer_version', 'download_filename', 'confirmation_sha256', 'expires_at', 'preview_id', 'created_by', 'created_at')
        changes = ' OR '.join(f'NEW.{field} IS DISTINCT FROM OLD.{field}' for field in frozen)
        _guard(connection, 'pdf_export_artifacts',
               f"OLD.status <> 'pending' OR NEW.status NOT IN ('ready','failed') OR {changes}")
        valid = ("NEW.active_version_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM pdf_integration_versions v "
                 "WHERE v.id = NEW.active_version_id AND v.integration_key = NEW.key AND v.status = 'published')")
        if connection.dialect.name == 'sqlite':
            for op in ('INSERT', 'UPDATE'):
                connection.exec_driver_sql(f'CREATE TRIGGER IF NOT EXISTS pdf_active_{op.lower()} BEFORE {op} '
                    f"ON pdf_integrations WHEN {valid} BEGIN SELECT RAISE(ABORT, 'Invalid active PDF version'); END")
        else:
            connection.exec_driver_sql("CREATE OR REPLACE FUNCTION pdf_active_guard() RETURNS trigger LANGUAGE plpgsql AS $$ "
                f"BEGIN IF {valid} THEN RAISE EXCEPTION 'Invalid active PDF version'; END IF; RETURN NEW; END $$")
            connection.exec_driver_sql('DROP TRIGGER IF EXISTS pdf_active_guard ON pdf_integrations')
            connection.exec_driver_sql('CREATE TRIGGER pdf_active_guard BEFORE INSERT OR UPDATE ON pdf_integrations '
                                      'FOR EACH ROW EXECUTE FUNCTION pdf_active_guard()')
