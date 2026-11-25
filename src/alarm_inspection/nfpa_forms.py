"""Request-local NFPA form identity; the empty ID preserves all legacy answers."""
from contextvars import ContextVar
from alarm_inspection.storage import NfpaForm

selected_form = ContextVar('nfpa_form', default='')


def validate_form(session, inspection_id, form_id):
    if not form_id:
        return session.query(NfpaForm).filter_by(inspection_id=inspection_id, is_original=True).first()
    row = session.get(NfpaForm, form_id)
    if row is None or row.inspection_id != inspection_id or row.is_original:
        raise ValueError('NFPA 72 form does not belong to this inspection.')
    return row
