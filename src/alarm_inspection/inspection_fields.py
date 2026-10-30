"""Persist native field labels/order/new-inspection defaults independently of answers."""
from datetime import datetime, timezone
from sqlalchemy import text
from alarm_inspection.domain.inspection_fields import NATIVE_FIELDS, STORE_TYPES
from alarm_inspection.storage import AppSetting

PREFIX = 'inspection_field:'


def definition_lock(session):
    # Serialize short definition mutations, including initially unsaved native settings.
    if session.get_bind().dialect.name == 'postgresql':
        session.execute(text('SELECT pg_advisory_xact_lock(7242031)'))
    elif session.get_bind().dialect.name == 'sqlite':
        session.connection().exec_driver_sql('BEGIN IMMEDIATE')


def native_fields(session):
    settings = {row.key: row.value for row in session.query(AppSetting).filter(AppSetting.key.like(PREFIX + '%'))}
    fields = []
    for index, (key, label, kind, limit) in enumerate(NATIVE_FIELDS):
        saved = {name: settings[PREFIX + key + ':' + name] for name in ('text', 'position', 'default_value') if PREFIX + key + ':' + name in settings}
        fields.append({'id': 'builtin:' + key, 'native_field': key, 'section': 'store_data',
                       'text': saved.get('text', label), 'input_type': kind, 'active': True,
                       'options': STORE_TYPES if key == 'store_type' else [], 'max_length': limit,
                       'default_value': saved.get('default_value', ''), 'position': int(saved.get('position', index - len(NATIVE_FIELDS)))})
    return fields


def save_native_field(session, field):
    for name in ('text', 'position', 'default_value'):
        key = PREFIX + field['native_field'] + ':' + name
        row = session.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key)
            session.add(row)
        row.value = str(field[name])
        row.updated_at = datetime.now(timezone.utc)
