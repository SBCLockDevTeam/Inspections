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
<style>body{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;color:#17202a}label{display:block;margin:14px 0 5px;font-weight:600}input,button{font:inherit;padding:9px;width:100%;box-sizing:border-box}button{margin-top:20px;background:#1769aa;color:#fff;border:0;border-radius:4px;cursor:pointer}.card{border:1px solid #d7dde3;border-radius:8px;padding:24px}#message{margin-top:20px;white-space:pre-wrap}.modal{display:none;position:fixed;inset:0;background:#0008;align-items:center;justify-content:center}.modal.open{display:flex}.modal-card{background:white;width:min(1000px,92vw);max-height:85vh;overflow:auto;border-radius:8px;padding:24px}.modal-card table{border-collapse:collapse;width:100%;margin-top:16px}.modal-card th,.modal-card td{border:1px solid #ccd3da;padding:8px;text-align:left}.modal-card th{background:#edf2f7}.accepted{color:#176b3a;font-weight:600}.review{color:#a33b00;font-weight:600}.close{width:auto;float:right;margin:0;background:#5b6470}</style></head>
<body><h1>Alarm Inspection Processor</h1><p>Create an inspection and upload its source files.</p>
<div class="card"><form id="inspection-form">
<label for="store_number">Store number</label><input id="store_number" required>
<label for="address">Address</label><input id="address" required>
<label for="start_date">Inspection start date</label><input id="start_date" type="date" required>
<label for="completion_date">Inspection completion date</label><input id="completion_date" type="date" required>
<label>Points Lists by security panel</label><div id="point-lists"><div class="point-list"><select name="point_list_category"><option>Fire</option><option>Burglar</option><option>Combo</option><option>Gas Station</option></select><input name="points_files" type="file" accept=".xls,.xlsx,.pdf" required></div></div><button type="button" id="add-list">Add another Points List</button><button type="button" id="preview-list">Preview first Points List</button><div id="preview"></div>
<label for="event_file">Event History (optional for now)</label><input id="event_file" type="file" accept=".xls,.xlsx,.pdf">
<button type="submit">Create inspection</button></form><div id="message"></div></div><div id="preview-modal" class="modal"><div class="modal-card"><button class="close" id="close-preview">Close</button><h2>Points List Preview</h2><p id="preview-summary"></p><table><thead><tr><th>Point</th><th>Description</th><th>Status</th><th>Reason</th><th>Source row</th></tr></thead><tbody id="preview-body"></tbody></table></div></div>
<script>const form=document.querySelector('#inspection-form');const msg=document.querySelector('#message');const lists=document.querySelector('#point-lists');const modal=document.querySelector('#preview-modal');const body=document.querySelector('#preview-body');const summary=document.querySelector('#preview-summary');document.querySelector('#close-preview').onclick=()=>modal.classList.remove('open');document.querySelector('#add-list').onclick=()=>{const row=lists.firstElementChild.cloneNode(true);row.querySelector('input').value='';row.querySelector('input').required=true;lists.appendChild(row)};document.querySelector('#preview-list').onclick=async()=>{const file=lists.querySelector('input').files[0];if(!file){msg.textContent='Choose an XLSX file first.';return}const data=new FormData();data.append('points_file',file);msg.textContent='Analyzing...';const r=await fetch('/api/point-lists/preview',{method:'POST',body:data});const j=await r.json();if(j.error){msg.textContent=j.error;return}summary.textContent='Accepted: '+j.accepted+' | Needs review: '+j.rejected+' | File: '+j.filename;body.innerHTML='';for(const row of j.rows){const tr=document.createElement('tr');tr.innerHTML='<td>'+String(row.address??'')+'</td><td>'+String(row.text??'')+'</td><td class="'+(row.accepted?'accepted':'review')+'">'+(row.accepted?'Accepted':'Review')+'</td><td>'+String(row.reason??'')+'</td><td>'+String(row.source_row??'')+'</td>';body.appendChild(tr)}modal.classList.add('open');msg.textContent='';};form.addEventListener('submit',async(e)=>{e.preventDefault();msg.textContent='Uploading and parsing...';const data=new FormData();for(const id of ['store_number','address','start_date','completion_date'])data.append(id,document.querySelector('#'+id).value);for(const row of document.querySelectorAll('.point-list')){data.append('point_list_categories',row.querySelector('select').value);data.append('points_files',row.querySelector('input').files[0]);}const event=document.querySelector('#event_file').files[0];if(event)data.append('event_file',event);const r=await fetch('/api/inspections',{method:'POST',body:data});const j=await r.json();if(!r.ok){msg.textContent='Error: '+(j.detail||'Upload failed');return}msg.textContent='Inspection '+j.id+' is ready for approval. Review the parsed data, then approve it.';const approve=document.createElement('button');approve.textContent='Approve parsed Points Lists';approve.onclick=async()=>{const a=await fetch('/api/inspections/'+j.id+'/approve-points',{method:'POST'});const result=await a.json();msg.textContent=result.status==='points_approved'?'Points Lists approved.':'Approval error: '+(result.error||'unknown error');};msg.appendChild(document.createElement('br'));msg.appendChild(approve);});</script>
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
        previews = []
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
        for filename in point_file_names:
            if filename.lower().endswith(".xlsx"):
                previews.append({"filename": filename, "rows": parse_xlsx(target / filename)})
        return {"id": inspection_id, "status": "pending_points_review", "files": files, "previews": previews}

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

    @app.post("/api/inspections/{inspection_id}/approve-points")
    def approve_points(inspection_id: str) -> dict:
        with store.begin() as session:
            row = session.get(Inspection, inspection_id)
            if row is None:
                return {"error": "inspection not found"}
            if row.status != "pending_points_review":
                return {"error": "inspection is not awaiting points review", "status": row.status}
            row.status = "points_approved"
        return {"id": inspection_id, "status": "points_approved"}

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
