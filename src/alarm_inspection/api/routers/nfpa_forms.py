"""Named NFPA 72 instances without replacing existing inspection evidence."""
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from alarm_inspection.storage import Inspection, NfpaForm, PanelType
from alarm_inspection.api.audit import record_decision


class FormName(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=40)

    @field_validator('name')
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Enter a form name.')
        return value


def create_router(store):
    router = APIRouter(prefix='/api/inspections/{inspection_id}/nfpa-forms')

    def check(session, ident):
        row = session.get(Inspection, ident)
        if row is None or row.status == 'deleted':
            raise HTTPException(404, 'Inspection not found.')

    def category(session, value):
        row = session.query(PanelType).filter_by(name_key=value.strip().casefold()).first()
        if row is None:
            raise HTTPException(422, 'Select a configured Points List Type.')
        return row.name

    @router.put('/{form_id}')
    def update(inspection_id: str, form_id: str, payload: FormName, request: Request):
        from alarm_inspection.nfpa_forms import validate_form
        with store.begin() as session:
            check(session, inspection_id)
            session.query(Inspection).filter_by(id=inspection_id).with_for_update().one()
            try:
                row = validate_form(session, inspection_id, '' if form_id == 'original' else form_id)
            except ValueError as exc:
                raise HTTPException(404, str(exc)) from exc
            kind = category(session, payload.category)
            previous = {'name': row.name, 'category': row.category} if row else {'name': 'NFPA 72 1 (original)', 'category': ''}
            if row is None:
                row = NfpaForm(id=str(uuid4()), inspection_id=inspection_id, is_original=True,
                               created_by=request.state.current_user.id, created_at=datetime.now(timezone.utc))
                session.add(row)
            row.name, row.category = payload.name, kind
            record_decision(session, request, inspection_id, '', 'nfpa_form_updated', {'id': form_id, 'previous': previous, 'name': row.name, 'category': row.category})
            return {'id': '' if row.is_original else row.id, 'name': row.name, 'category': row.category}

    @router.get('')
    def forms(inspection_id: str):
        with store() as session:
            check(session, inspection_id)
            rows = session.query(NfpaForm).filter_by(inspection_id=inspection_id).order_by(NfpaForm.created_at, NfpaForm.id).all()
            original = next((r for r in rows if r.is_original), None)
            return {'forms': [{'id': '', 'name': original.name if original else 'NFPA 72 1 (original)', 'category': original.category if original else ''}] + [
                {'id': row.id, 'name': row.name, 'category': row.category} for row in rows if not row.is_original]}


    @router.post('', status_code=201)
    def create(inspection_id: str, payload: FormName, request: Request):
        with store.begin() as session:
            check(session, inspection_id)
            row = NfpaForm(id=str(uuid4()), inspection_id=inspection_id, name=payload.name, category=category(session, payload.category),
                           created_by=request.state.current_user.id, created_at=datetime.now(timezone.utc))
            session.add(row)
            record_decision(session, request, inspection_id, "", "nfpa_form_created", {"id": row.id, "name": row.name, "category": row.category})
            return {'id': row.id, 'name': row.name, 'category': row.category}

    return router
