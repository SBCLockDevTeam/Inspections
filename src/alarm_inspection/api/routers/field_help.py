"""Shared field help with administrator authoring and private, bounded media."""
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, StrictBool
from alarm_inspection.api.common import UPLOAD_ROOT
from alarm_inspection.api.routers.inspection_tasks import admin_only, serialize_task
from alarm_inspection.inspection_fields import native_fields, definition_lock
from alarm_inspection.storage import FieldHelp, HelpMedia, InspectionTask


class HelpUpdate(BaseModel):
    enabled: StrictBool
    body: str = Field(max_length=20000)
    media: list[str] = Field(default_factory=list, max_length=20)
    revision: int = Field(ge=0)


def catalog(session):
    return [*native_fields(session), *[serialize_task(t) for t in session.query(InspectionTask).order_by(InspectionTask.position).all()],
            *[{"id": "nfpa:" + key, "text": label, "section": "nfpa72", "active": True} for key, label in [("name", "NFPA 72 form name"), ("type", "NFPA 72 Points List Type")]],
            *[{"id": "points:" + key, "text": label, "section": "points", "active": True} for key, label in
              [("upload", "Points List upload"), ("category", "Panel type"), ("events", "Event History upload"),
               ("description", "Point description"), ("status", "Point review status"), ("location", "Device location"), ("result", "Test result")]]]


def check_field(session, field_id):
    if not any(f['id'] == field_id for f in catalog(session)):
        raise HTTPException(404, 'Field not found.')


def serialize(row):
    return {"enabled": row.enabled, "body": row.body, "media": json.loads(row.media_json), "revision": row.revision} if row else {"enabled": False, "body": "", "media": [], "revision": 0}


def create_router(store):
    router = APIRouter(tags=['field-help'])
    root = UPLOAD_ROOT / 'field-help'

    @router.get('/api/help')
    def read_help():
        with store() as session:
            return {r.field_id: serialize(r) for r in session.query(FieldHelp).filter(FieldHelp.enabled.is_(True))}

    @router.get('/api/admin/help', dependencies=[Depends(admin_only)])
    def admin_help():
        with store() as session:
            saved = {r.field_id: r for r in session.query(FieldHelp)}
            return {'fields': [{**f, 'help': serialize(saved.get(f['id']))} for f in catalog(session)]}

    @router.put('/api/admin/help/{field_id}', dependencies=[Depends(admin_only)])
    def save_help(field_id: str, payload: HelpUpdate, request: Request):
        with store.begin() as session:
            definition_lock(session)
            check_field(session, field_id)
            row = session.get(FieldHelp, field_id)
            if payload.revision != (row.revision if row else 0):
                raise HTTPException(409, 'Help changed on another device. Reopen the configuration before saving.')
            media = []
            for ident in dict.fromkeys(payload.media):
                item = session.get(HelpMedia, ident)
                if item is None or item.field_id != field_id:
                    raise HTTPException(422, 'Invalid help attachment.')
                media.append({'id': item.id, 'type': item.content_type, 'name': item.filename})
            if sum(m['type'].startswith('video/') for m in media) > 1:
                raise HTTPException(422, 'Use one video per field.')
            if row is None:
                row = FieldHelp(field_id=field_id)
                session.add(row)
            row.enabled, row.body, row.media_json = payload.enabled, payload.body, json.dumps(media)
            row.revision = payload.revision + 1
            row.updated_by = request.state.current_user.id
            row.updated_at = datetime.now(timezone.utc)
            session.flush()
            return serialize(row)

    @router.post('/api/admin/help/{field_id}/media', dependencies=[Depends(admin_only)])
    async def upload(field_id: str, file: UploadFile = File(...)):
        with store() as session:
            check_field(session, field_id)
        ident = str(uuid4())
        root.mkdir(parents=True, exist_ok=True)
        path = root / ident
        total = 0
        header = b''
        try:
            with path.open('xb') as out:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > 50 * 1024 * 1024:
                        raise HTTPException(413, 'Help media must be 50 MB or smaller.')
                    if not header:
                        header = chunk[:32]
                    out.write(chunk)
            kind = None
            if header.startswith(b'\x89PNG\r\n\x1a\n'): kind = 'image/png'
            elif header.startswith(b'\xff\xd8\xff'): kind = 'image/jpeg'
            elif header[:4] == b'RIFF' and header[8:12] == b'WEBP': kind = 'image/webp'
            elif header[4:8] == b'ftyp' and header[8:12] in (b'isom', b'iso2', b'mp41', b'mp42', b'avc1', b'M4V '): kind = 'video/mp4'
            elif header.startswith(b'\x1aE\xdf\xa3'): kind = 'video/webm'
            if kind is None:
                raise HTTPException(422, 'Use a PNG, JPEG, WebP picture or MP4/WebM video.')
            with store.begin() as session:
                session.add(HelpMedia(id=ident, field_id=field_id, content_type=kind, filename=(file.filename or 'Help media')[:255]))
            return {'id': ident, 'type': kind, 'name': (file.filename or 'Help media')[:255]}
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    @router.get('/api/help/media/{ident}')
    def media(ident: str, request: Request):
        with store() as session:
            item = session.get(HelpMedia, ident)
            if item is None:
                raise HTTPException(404)
            help_row = session.get(FieldHelp, item.field_id)
            if not request.state.current_user.is_admin and (not help_row or not help_row.enabled or ident not in [m['id'] for m in json.loads(help_row.media_json)]):
                raise HTTPException(404)
            return FileResponse(root / item.id, media_type=item.content_type, headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})

    return router
