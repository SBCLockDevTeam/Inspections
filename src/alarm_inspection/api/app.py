"""HTTP API and small browser UI for the first usable application slice."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from alarm_inspection.domain.points import normalize_point
from alarm_inspection.storage import (
    Inspection,
    PointDecision,
    PointList,
    PointListDecision,
    PointListEventDate,
    SourceFile,
    open_store,
)
from alarm_inspection.intake.event_history import parse_xlsx as parse_event_history_xlsx
from alarm_inspection.intake.points_list import parse_xlsx

try:
    from fastapi import Body, FastAPI, File, Form, Query, UploadFile
    from fastapi.responses import HTMLResponse, Response
except ImportError:  # Allows domain tests to run without web dependencies.
    FastAPI = None


_UPLOAD_ROOT = Path("/tmp/alarm-inspection-uploads")


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off", ""}:
        return False
    return default


def _format_event_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _parse_saved_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text, text.replace(" ", "T", 1)):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None

_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alarm Inspection Processor</title>
<style>body{font-family:system-ui,sans-serif;max-width:980px;margin:40px auto;padding:0 20px;color:#17202a}h1{margin-bottom:8px}label{display:block;margin:14px 0 5px;font-weight:600}input,button,select{font:inherit;padding:9px;width:100%;box-sizing:border-box}button{margin-top:12px;background:#1769aa;color:#fff;border:0;border-radius:4px;cursor:pointer}.secondary{background:#5b6470}.ghost{background:#fff;color:#1769aa;border:1px solid #1769aa}.danger{background:#b3261e}.card{border:1px solid #d7dde3;border-radius:8px;padding:24px;margin-top:16px}.hidden{display:none}.row{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:end}.table{border-collapse:collapse;width:100%;margin-top:16px}.table th,.table td{border:1px solid #ccd3da;padding:8px;text-align:left}.table th{background:#edf2f7}#message,#inspection-message{margin-top:16px;white-space:pre-wrap}.modal{display:none;position:fixed;inset:0;background:#0008;align-items:center;justify-content:center}.modal.open{display:flex}.modal-card{background:white;width:min(1000px,92vw);max-height:85vh;overflow:auto;border-radius:8px;padding:24px}.accepted-row{background:#e8f5e9}.review-row{background:#ffebee}.accepted{color:#176b3a;font-weight:600}.review{color:#a33b00;font-weight:600}.status-toggle{width:auto;margin:0;padding:5px 10px;background:#fff;border:1px solid currentColor}.close{width:auto;float:right;margin:0;background:#5b6470}.nav{display:flex;gap:8px;align-items:center;flex-wrap:nowrap;overflow-x:auto}.nav button{width:auto;margin-top:0;white-space:nowrap}.inline-form{display:flex;gap:8px;align-items:center;margin:0;flex:1 1 auto}.inline-form label{display:none}.inline-form input[type=file]{margin:0;width:320px;max-width:42vw;padding:7px}.inline-form button{width:auto;margin-top:0;white-space:nowrap}.point-list{display:grid;grid-template-columns:180px 1fr auto;gap:8px;align-items:center;margin-top:8px}.point-list select,.point-list input{margin:0}.point-list .remove-point-list{width:auto;margin-top:0;white-space:nowrap}.create-actions{display:flex;gap:8px;align-items:center;flex-wrap:nowrap;overflow-x:auto;margin-top:12px}.create-actions button{width:auto;margin-top:0;white-space:nowrap}</style></head>
<body><h1>Alarm Inspection Processor</h1><p>Choose an existing inspection or create a new one.</p>

<div id="home-screen" class="card">
<h2>Start</h2>
<label for="inspection-picker">Existing inspections</label>
<div class="row"><select id="inspection-picker"></select><button type="button" id="open-inspection" class="ghost">Open Inspection</button></div>
<button type="button" id="refresh-inspections" class="secondary">Refresh List</button>
<button type="button" id="start-create">Create New Inspection</button>
<div id="home-message"></div>
</div>

<div id="create-screen" class="card hidden">
<div class="nav"><button type="button" id="back-home-from-create" class="secondary">Back to Home</button></div>
<h2>Create New Inspection</h2>
<form id="inspection-form">
<label for="store_number">Store number</label><input id="store_number" required>
<label for="address">Address</label><input id="address" required>
<label>Points Lists by security panel</label><div id="point-lists"><div class="point-list"><select name="point_list_category" required><option>Combo</option><option>Fire</option><option>Burglar</option><option>Gas Station</option></select><input name="points_files" type="file" accept=".xls,.xlsx,.pdf" required><button type="button" class="remove-point-list danger">Delete List</button></div></div><div class="create-actions"><button type="button" id="add-list">Add another Points List</button><button type="button" id="preview-list">Preview Points Lists</button><button type="submit">Create Inspection</button></div><div id="preview"></div>
<input type="hidden" name="point_decisions" id="point-decisions" value="[]"></form><div id="message"></div></div>

<div id="inspection-screen" class="card hidden">
<div class="nav"><button type="button" id="back-home-from-inspection" class="secondary">Back to Home</button><button type="button" id="refresh-inspection" class="ghost">Refresh Inspection</button><button type="button" id="toggle-missing-points" class="ghost">Show Missing Points Only</button></div>
<div class="nav"><form id="event-history-form" class="inline-form"><label for="event-file">Event History file</label><input id="event-file" type="file" accept=".xls,.xlsx,.pdf" required><button type="submit">Upload Event History</button></form><button type="button" id="save-event-dates" class="ghost">Save Matched Dates</button><button type="button" id="clear-event-dates" class="secondary">Clear Dates</button></div>
<h2 id="inspection-title">Inspection</h2>
<p id="inspection-meta"></p>
<label for="inspection-point-list-selector">Points List</label><select id="inspection-point-list-selector"></select>
<h3>Accepted Points</h3>
<table class="table"><thead><tr><th>Point</th><th>Description</th><th>Date</th></tr></thead><tbody id="accepted-points-body"></tbody></table>
<div id="inspection-message"></div>
</div>

<div id="preview-modal" class="modal"><div class="modal-card"><button class="close" id="close-preview">Close</button><h2>Points List Review</h2><label for="preview-list-selector">Points List</label><select id="preview-list-selector"></select><p id="preview-summary"></p><p>Edit descriptions and use each row's status button to toggle Accept or Review. Rows remain visible until you delete them.</p><div class="nav"><button type="button" class="accept-review-action">Accept all Review rows</button><button type="button" class="delete-review-action">Delete all Review rows</button><button type="button" class="save-review-action">Save review decisions</button></div><table class="table"><thead><tr><th>Point</th><th>Description</th><th>Status</th></tr></thead><tbody id="preview-body"></tbody></table><div class="nav"><button type="button" class="accept-review-action">Accept all Review rows</button><button type="button" class="delete-review-action">Delete all Review rows</button><button type="button" class="save-review-action">Save review decisions</button></div></div></div>
<script src="/review.js"></script>
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

    @app.get("/review.js")
    def review_script() -> Response:
        script = Path(__file__).with_name("review.js").read_text(encoding="utf-8")
        return Response(content=script, media_type="application/javascript")

    @app.post("/api/inspections")
    async def create_inspection(
        store_number: str = Form(...),
        address: str = Form(...),
        point_list_categories: list[str] = Form(...),
        points_files: list[UploadFile] = File(...),
        point_decisions: str = Form("[]"),
    ) -> dict:
        inspection_id = str(uuid4())
        target = _UPLOAD_ROOT / inspection_id
        target.mkdir(parents=True, exist_ok=True)
        files = []
        point_file_names = []
        for upload in points_files:
            filename = Path(upload.filename or "upload.bin").name
            destination = target / filename
            destination.write_bytes(await upload.read())
            files.append(filename)
            point_file_names.append(filename)
        created_at = datetime.now(timezone.utc)
        inferred_date = date.today()

        parsed_decisions = []
        for filename in point_file_names:
            if filename.lower().endswith(".xlsx"):
                parsed_decisions.extend(parse_xlsx(target / filename))

        submitted_decisions = json.loads(point_decisions)
        decisions_to_store = submitted_decisions if submitted_decisions else parsed_decisions

        with store.begin() as session:
            session.add(Inspection(id=inspection_id, store_number=store_number, address=address,
                                   start_date=inferred_date, completion_date=inferred_date,
                                   status="pending_event_history", created_at=created_at))
            for filename in files:
                session.add(SourceFile(id=str(uuid4()), inspection_id=inspection_id,
                                       filename=filename, path=str(target / filename),
                                       kind="points_list"))
            point_list_ids_by_filename: dict[str, str] = {}
            for filename, list_category in zip(point_file_names, point_list_categories, strict=False):
                point_list_id = str(uuid4())
                session.add(PointList(id=point_list_id, inspection_id=inspection_id,
                                      category=list_category, filename=filename,
                                      path=str(target / filename), accepted_at=created_at))
                point_list_ids_by_filename[filename] = point_list_id

            default_list_id = point_list_ids_by_filename.get(point_file_names[0], "") if point_file_names else ""
            for decision in decisions_to_store:
                source_filename = str(decision.get("source_filename") or "")
                point_list_id = point_list_ids_by_filename.get(source_filename, default_list_id)
                session.add(PointDecision(id=str(uuid4()), inspection_id=inspection_id,
                                          address=decision.get("address"), text=decision.get("text", ""),
                                          accepted=_as_bool(decision.get("accepted"), default=False),
                                          deleted=_as_bool(decision.get("deleted"), default=False),
                                          reason=decision.get("reason", "technician review")))
                if point_list_id:
                    session.add(PointListDecision(
                        id=str(uuid4()),
                        inspection_id=inspection_id,
                        point_list_id=point_list_id,
                        address=decision.get("address"),
                        text=decision.get("text", ""),
                        accepted=_as_bool(decision.get("accepted"), default=False),
                        deleted=_as_bool(decision.get("deleted"), default=False),
                        reason=decision.get("reason", "technician review"),
                    ))
        return {
            "id": inspection_id,
            "status": "pending_event_history",
            "files": files,
            "accepted_points": sum(1 for d in decisions_to_store if _as_bool(d.get("accepted"), default=False)),
        }

    @app.get("/api/inspections")
    def list_inspections() -> list[dict]:
        with store() as session:
            rows = session.query(Inspection).order_by(Inspection.created_at.desc()).all()
            return [{"id": row.id, "store_number": row.store_number, "address": row.address,
                     "start_date": row.start_date.isoformat(),
                     "completion_date": row.completion_date.isoformat(),
                     "status": row.status, "created_at": row.created_at.isoformat()} for row in rows]

    @app.get("/api/inspections/{inspection_id}")
    def get_inspection(inspection_id: str, point_list_id: str | None = Query(default=None)) -> dict:
        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            point_lists = (
                session.query(PointList)
                .filter(PointList.inspection_id == inspection_id)
                .order_by(PointList.accepted_at.asc(), PointList.filename.asc())
                .all()
            )
            selected_point_list_id = point_list_id or (point_lists[0].id if point_lists else None)

            scoped_points = (
                session.query(PointListDecision)
                .filter(
                    PointListDecision.inspection_id == inspection_id,
                    PointListDecision.point_list_id == selected_point_list_id,
                    PointListDecision.accepted.is_(True),
                    PointListDecision.deleted.is_(False),
                )
                .order_by(PointListDecision.address.asc(), PointListDecision.text.asc())
                .all()
            )
            if scoped_points:
                points = scoped_points
            else:
                points = (
                    session.query(PointDecision)
                    .filter(
                        PointDecision.inspection_id == inspection_id,
                        PointDecision.accepted.is_(True),
                        PointDecision.deleted.is_(False),
                    )
                    .order_by(PointDecision.address.asc(), PointDecision.text.asc())
                    .all()
                )

            selected_kind = f"event_history:{selected_point_list_id}" if selected_point_list_id else "event_history"
            event_history_files = (
                session.query(SourceFile)
                .filter(SourceFile.inspection_id == inspection_id, SourceFile.kind == selected_kind)
                .order_by(SourceFile.filename.asc())
                .all()
            )
            saved_event_dates = (
                session.query(PointListEventDate)
                .filter(
                    PointListEventDate.inspection_id == inspection_id,
                    PointListEventDate.point_list_id == selected_point_list_id,
                )
                .order_by(PointListEventDate.point_address.asc())
                .all()
            )
            mapped_dates = {item.point_address: item.event_timestamp for item in saved_event_dates}
            return {
                "id": inspection.id,
                "store_number": inspection.store_number,
                "address": inspection.address,
                "start_date": inspection.start_date.isoformat(),
                "completion_date": inspection.completion_date.isoformat(),
                "status": inspection.status,
                "accepted_points": [
                    {
                        "address": point.address,
                        "text": point.text,
                        "event_date": _format_event_date(
                            mapped_dates.get(point.address) if point.address is not None else None
                        ),
                    }
                    for point in points
                ],
                "point_lists": [
                    {"id": item.id, "category": item.category, "filename": item.filename}
                    for item in point_lists
                ],
                "selected_point_list_id": selected_point_list_id,
                "event_history_files": [file.filename for file in event_history_files],
            }

    @app.post("/api/inspections/{inspection_id}/event-history")
    async def add_event_history(
        inspection_id: str,
        point_list_id: str = Form(...),
        event_file: UploadFile = File(...),
    ) -> dict:
        target = _UPLOAD_ROOT / inspection_id
        if not target.exists():
            return {"error": "inspection not found"}

        with store() as session:
            point_list = (
                session.query(PointList)
                .filter(PointList.inspection_id == inspection_id, PointList.id == point_list_id)
                .first()
            )
            if point_list is None:
                return {"error": "Selected Points List was not found for this inspection."}

        filename = Path(event_file.filename or "event-history.bin").name
        if not filename.lower().endswith(".xlsx"):
            return {"error": "Event History processing currently supports XLSX files."}
        destination = target / filename
        destination.write_bytes(await event_file.read())
        try:
            extracted = parse_event_history_xlsx(destination)
        except ValueError as exc:
            destination.unlink(missing_ok=True)
            return {"error": f"{filename}: {exc}"}

        with store() as session:
            existing = (
                session.query(PointListEventDate)
                .filter(
                    PointListEventDate.inspection_id == inspection_id,
                    PointListEventDate.point_list_id == point_list_id,
                )
                .all()
            )
        existing_points = {item.point_address for item in existing}

        pending_matches = [
            {"point": point, "timestamp": _format_event_date(timestamp)}
            for point, timestamp in sorted(extracted.items())
            if point not in existing_points
        ]

        with store.begin() as session:
            session.add(SourceFile(id=str(uuid4()), inspection_id=inspection_id,
                                   filename=filename, path=str(destination),
                                   kind=f"event_history:{point_list_id}"))
        return {
            "inspection_id": inspection_id,
            "point_list_id": point_list_id,
            "filename": filename,
            "status": "matched",
            "matched_points": len(extracted),
            "pending_matches": pending_matches,
            "ignored_existing": len(extracted) - len(pending_matches),
        }

    @app.post("/api/inspections/{inspection_id}/event-dates/save")
    def save_event_dates(inspection_id: str, payload: dict = Body(default={})) -> dict:
        matches = payload.get("matches", [])
        point_list_id = str(payload.get("point_list_id") or "").strip()
        if not isinstance(matches, list):
            return {"error": "matches must be a list"}
        if not point_list_id:
            return {"error": "point_list_id is required"}

        saved = 0
        ignored_existing = 0
        ignored_invalid = 0

        with store.begin() as session:
            point_list = (
                session.query(PointList)
                .filter(PointList.inspection_id == inspection_id, PointList.id == point_list_id)
                .first()
            )
            if point_list is None:
                return {"error": "Selected Points List was not found for this inspection."}

            existing_rows = (
                session.query(PointListEventDate)
                .filter(
                    PointListEventDate.inspection_id == inspection_id,
                    PointListEventDate.point_list_id == point_list_id,
                )
                .all()
            )
            existing_points = {item.point_address for item in existing_rows}

            accepted_points = (
                session.query(PointListDecision)
                .filter(
                    PointListDecision.inspection_id == inspection_id,
                    PointListDecision.point_list_id == point_list_id,
                    PointListDecision.accepted.is_(True),
                    PointListDecision.deleted.is_(False),
                    PointListDecision.address.is_not(None),
                )
                .all()
            )
            allowed_points = {int(item.address) for item in accepted_points if item.address is not None}
            if not allowed_points:
                fallback_points = (
                    session.query(PointDecision)
                    .filter(
                        PointDecision.inspection_id == inspection_id,
                        PointDecision.accepted.is_(True),
                        PointDecision.deleted.is_(False),
                        PointDecision.address.is_not(None),
                    )
                    .all()
                )
                allowed_points = {int(item.address) for item in fallback_points if item.address is not None}

            for item in matches:
                if not isinstance(item, dict):
                    ignored_invalid += 1
                    continue
                point = normalize_point(item.get("point"))
                timestamp = _parse_saved_timestamp(item.get("timestamp"))
                source_filename = str(item.get("source_filename") or "")

                if point is None or timestamp is None or point not in allowed_points:
                    ignored_invalid += 1
                    continue
                if point in existing_points:
                    ignored_existing += 1
                    continue

                session.add(
                    PointListEventDate(
                        id=str(uuid4()),
                        inspection_id=inspection_id,
                        point_list_id=point_list_id,
                        point_address=point,
                        event_timestamp=timestamp,
                        source_filename=source_filename,
                    )
                )
                existing_points.add(point)
                saved += 1

        return {
            "inspection_id": inspection_id,
            "point_list_id": point_list_id,
            "status": "saved",
            "saved": saved,
            "ignored_existing": ignored_existing,
            "ignored_invalid": ignored_invalid,
        }

    @app.post("/api/inspections/{inspection_id}/event-dates/clear")
    def clear_event_dates(inspection_id: str, payload: dict = Body(default={})) -> dict:
        point_list_id = str(payload.get("point_list_id") or "").strip()
        if not point_list_id:
            return {"error": "point_list_id is required"}
        with store.begin() as session:
            cleared = (
                session.query(PointListEventDate)
                .filter(
                    PointListEventDate.inspection_id == inspection_id,
                    PointListEventDate.point_list_id == point_list_id,
                )
                .delete(synchronize_session=False)
            )
        return {
            "inspection_id": inspection_id,
            "point_list_id": point_list_id,
            "status": "cleared",
            "cleared": int(cleared),
        }

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
    async def preview_points_list(
        points_files: list[UploadFile] = File(...),
        point_list_categories: list[str] = Form(default=[]),
    ) -> dict:
        if point_list_categories and len(point_list_categories) != len(points_files):
            return {"error": "Each Points List must have a matching security-panel category."}

        previews = []
        for index, points_file in enumerate(points_files):
            filename = Path(points_file.filename or f"points-{index + 1}.xlsx").name
            if not filename.lower().endswith(".xlsx"):
                return {"error": "The first parser supports XLSX files; PDF and legacy XLS need a separate adapter."}
            preview_path = _UPLOAD_ROOT / f"preview-{uuid4()}-{filename}"
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.write_bytes(await points_file.read())
            try:
                rows = parse_xlsx(preview_path)
            except ValueError as exc:
                return {"error": f"{filename}: {exc}"}
            previews.append({
                "filename": filename,
                "category": point_list_categories[index] if point_list_categories else "",
                "accepted": sum(row["accepted"] for row in rows),
                "rejected": sum(not row["accepted"] for row in rows),
                "rows": rows,
            })

        accepted = sum(item["accepted"] for item in previews)
        rejected = sum(item["rejected"] for item in previews)
        first = previews[0] if len(previews) == 1 else None
        return {
            "filename": first["filename"] if first else None,
            "accepted": accepted,
            "rejected": rejected,
            "rows": first["rows"] if first else [],
            "lists": previews,
        }

    return app


app = create_app() if FastAPI is not None else None
