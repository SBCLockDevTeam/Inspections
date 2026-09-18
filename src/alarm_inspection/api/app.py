"""HTTP API and small browser UI for the first usable application slice."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

try:
    from fastapi import FastAPI, File, Form, UploadFile
    from fastapi.responses import HTMLResponse
except ImportError:  # Allows domain tests to run without web dependencies.
    FastAPI = None


_INSPECTIONS: dict[str, dict] = {}
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
<label for="points_file">Points List</label><input id="points_file" type="file" accept=".xls,.xlsx,.pdf" required>
<label for="event_file">Event History (optional for now)</label><input id="event_file" type="file" accept=".xls,.xlsx,.pdf">
<button>Create inspection</button></form><div id="message"></div></div>
<script>const form=document.querySelector('#inspection-form');const msg=document.querySelector('#message');form.addEventListener('submit',async(e)=>{e.preventDefault();msg.textContent='Uploading...';const data=new FormData();for(const id of ['store_number','address','start_date','completion_date'])data.append(id,document.querySelector('#'+id).value);data.append('points_file',document.querySelector('#points_file').files[0]);const event=document.querySelector('#event_file').files[0];if(event)data.append('event_file',event);const r=await fetch('/api/inspections',{method:'POST',body:data});const j=await r.json();msg.textContent=r.ok?'Inspection created: '+j.id:'Error: '+(j.detail||'Upload failed');});</script>
</body></html>"""


def create_app():
    if FastAPI is None:
        raise RuntimeError("Install the 'web' optional dependencies to run the API")
    app = FastAPI(title="Alarm Inspection Processor", version="0.1.0")

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
        points_file: UploadFile = File(...),
        event_file: UploadFile | None = File(None),
    ) -> dict:
        inspection_id = str(uuid4())
        target = _UPLOAD_ROOT / inspection_id
        target.mkdir(parents=True, exist_ok=True)
        files = []
        for upload in (points_file, event_file):
            if upload is None:
                continue
            filename = Path(upload.filename or "upload.bin").name
            destination = target / filename
            destination.write_bytes(await upload.read())
            files.append(filename)
        _INSPECTIONS[inspection_id] = {
            "id": inspection_id,
            "store_number": store_number,
            "address": address,
            "start_date": start_date.isoformat(),
            "completion_date": completion_date.isoformat(),
            "files": files,
            "status": "received",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return _INSPECTIONS[inspection_id]

    @app.get("/api/inspections")
    def list_inspections() -> list[dict]:
        return list(_INSPECTIONS.values())

    return app


app = create_app() if FastAPI is not None else None
