"""HTTP API and small browser UI for the first usable application slice."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from alarm_inspection.storage import Inspection, PointList, SourceFile, open_store
from alarm_inspection.intake.points_list import parse_xlsx

try:
    from fastapi import FastAPI, File, Form, UploadFile
    from fastapi.responses import HTMLResponse
except ImportError:  # Allows domain tests to run without web dependencies.
    FastAPI = None


_UPLOAD_ROOT = Path("/tmp/alarm-inspection-uploads")

_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alarm Inspection Processor</title>
<style>body{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;color:#17202a}label{display:block;margin:14px 0 5px;font-weight:600}input,button{font:inherit;padding:9px;width:100%;box-sizing:border-box}button{margin-top:20px;background:#1769aa;color:#fff;border:0;border-radius:4px;cursor:pointer}.card{border:1px solid #d7dde3;border-radius:8px;padding:24px}#message{margin-top:20px;white-space:pre-wrap}</style></head>
<body><h1>Alarm Inspection Processor</h1><p>Create an inspection and upload its source files.</p>
<div class="card"><form id="inspection-form">
<label for="store_number">Store number</label><input id="store_number" required>
<label for="address">Address</label><input id="address" required>
<label for="start_date">Inspection start date</label><input id="start_date" type="date" required>
<label for="completion_date">Inspection completion date</label><input id="completion_date" type="date" required>
<label>Points Lists by security panel</label><div id="point-lists"><div class="point-list"><select name="point_list_category"><option>Fire</option><option>Burglar</option><option>Combo</option><option>Gas Station</option></select><input name="points_files" type="file" accept=".xls,.xlsx,.pdf" required></div></div><button type="button" id="add-list">Add another Points List</button>
<label for="event_file">Event History (optional for now)</label><input id="event_file" type="file" accept=".xls,.xlsx,.pdf">
<button type="submit">Create inspection</button></form><div id="message"></div></div>
<script>const form=document.querySelector('#inspection-form');const msg=document.querySelector('#message');const lists=document.querySelector('#point-lists');document.querySelector('#add-list').onclick=()=>{const row=lists.firstElementChild.cloneNode(true);row.querySelector('input').value='';row.querySelector('input').required=true;lists.appendChild(row)};form.addEventListener('submit',async(e)=>{e.preventDefault();msg.textContent='Uploading...';const data=new FormData();for(const id of ['store_number','address','start_date','completion_date'])data.append(id,document.querySelector('#'+id).value);for(const row of document.querySelectorAll('.point-list')){data.append('point_list_categories',row.querySelector('select').value);data.append('points_files',row.querySelector('input').files[0]);}const event=document.querySelector('#event_file').files[0];if(event)data.append('event_file',event);const r=await fetch('/api/inspections',{method:'POST',body:data});const j=await r.json();msg.textContent=r.ok?'Inspection created: '+j.id+'. Additional Event History can be uploaded to /api/inspections/'+j.id+'/event-history':'Error: '+(j.detail||'Upload failed');});</script>
</body></html>"""


def create_app():
    if FastAPI is None:
        raise RuntimeError("Install the 'web' optional dependencies to run the API")
    app = FastAPI(title="Alarm Inspection Processor", version="0.1.0")
    store = open_store()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return _HTML

    @app.post("/api/inspections")
    async def create_inspection(
        store_number: str = Form(...),
        address: str = Form(...),
        start_date: date = Form(...),
        completion_date: date = Form(...),
        point_list_categories: list[str] = Form(...),
        points_files: list[UploadFile] = File(...),
        event_file: UploadFile | None = File(None),
    ) -> dict:
        inspection_id = str(uuid4())
        target = _UPLOAD_ROOT / inspection_id
        target.mkdir(parents=True, exist_ok=True)
        files = []
        point_file_names = []
        for upload in (*points_files, event_file):
            if upload is None:
                continue
            filename = Path(upload.filename or "upload.bin").name
            destination = target / filename
            destination.write_bytes(await upload.read())
            files.append(filename)
            if upload in points_files:
                point_file_names.append(filename)
        created_at = datetime.now(timezone.utc)
        with store.begin() as session:
            session.add(Inspection(id=inspection_id, store_number=store_number, address=address,
                                   start_date=start_date, completion_date=completion_date,
                                   status="received", created_at=created_at))
            for filename in files:
                session.add(SourceFile(id=str(uuid4()), inspection_id=inspection_id,
                                       filename=filename, path=str(target / filename),
                                       kind="points_list" if filename in point_file_names else "event_history"))
            for filename, list_category in zip(point_file_names, point_list_categories, strict=False):
                session.add(PointList(id=str(uuid4()), inspection_id=inspection_id,
                                      category=list_category, filename=filename,
                                      path=str(target / filename), accepted_at=created_at))
        return {"id": inspection_id, "status": "received", "files": files}

    @app.get("/api/inspections")
    def list_inspections() -> list[dict]:
        with store() as session:
            rows = session.query(Inspection).order_by(Inspection.created_at.desc()).all()
            return [{"id": row.id, "store_number": row.store_number, "address": row.address,
                     "start_date": row.start_date.isoformat(),
                     "completion_date": row.completion_date.isoformat(),
                     "status": row.status, "created_at": row.created_at.isoformat()} for row in rows]

    @app.post("/api/inspections/{inspection_id}/event-history")
    async def add_event_history(inspection_id: str, event_file: UploadFile = File(...)) -> dict:
        target = _UPLOAD_ROOT / inspection_id
        if not target.exists():
            return {"error": "inspection not found"}
        filename = Path(event_file.filename or "event-history.bin").name
        destination = target / filename
        destination.write_bytes(await event_file.read())
        with store.begin() as session:
            session.add(SourceFile(id=str(uuid4()), inspection_id=inspection_id,
                                   filename=filename, path=str(destination), kind="event_history"))
        return {"inspection_id": inspection_id, "filename": filename, "status": "received"}

    @app.post("/api/point-lists/preview")
    async def preview_points_list(points_file: UploadFile = File(...)) -> dict:
        filename = Path(points_file.filename or "points.xlsx").name
        if not filename.lower().endswith(".xlsx"):
            return {"error": "The first parser supports XLSX files; PDF and legacy XLS need a separate adapter."}
        preview_path = _UPLOAD_ROOT / f"preview-{uuid4()}-{filename}"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_bytes(await points_file.read())
        try:
            rows = parse_xlsx(preview_path)
            return {"filename": filename, "accepted": sum(row["accepted"] for row in rows),
                    "rejected": sum(not row["accepted"] for row in rows), "rows": rows}
        except ValueError as exc:
            return {"error": str(exc)}

    return app


app = create_app() if FastAPI is not None else None
