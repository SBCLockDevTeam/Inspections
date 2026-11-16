from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import Body, File, Form, HTTPException, Request, UploadFile

from alarm_inspection.api.audit import record_decision

from alarm_inspection.api.common import (
    ensure_inspection_upload_dir,
    event_history_kind,
    format_event_date,
    parse_saved_timestamp,
)
from alarm_inspection.domain.points import normalize_point
from alarm_inspection.domain.event_status import missing_event_for_marked_device
from alarm_inspection.intake.event_history import parse_xlsx as parse_event_history_xlsx
from alarm_inspection.storage import (
    Inspection,
    PointList,
    PointListDecision,
    PointListEventDate,
    PointListPendingEventDate,
    SourceFile,
)


def _merge_events(session, inspection_id, point_list_id, extracted, filename):
    existing = session.query(PointListEventDate).filter_by(inspection_id=inspection_id, point_list_id=point_list_id).all()
    existing_points = {item.point_address for item in existing}
    decisions = session.query(PointListDecision).filter_by(inspection_id=inspection_id, point_list_id=point_list_id, accepted=True, deleted=False).all()
    allowed_points = {item.address for item in decisions if item.address is not None}
    pending = {item.point_address: item for item in session.query(PointListPendingEventDate).filter_by(inspection_id=inspection_id, point_list_id=point_list_id).all()}
    for point, timestamp in extracted.items():
        if point in existing_points or point not in allowed_points:
            continue
        previous = pending.get(point)
        if previous is None:
            previous = PointListPendingEventDate(inspection_id=inspection_id, point_list_id=point_list_id,
                point_address=point, event_timestamp=timestamp, source_filename=filename)
            session.add(previous)
            pending[point] = previous
        elif timestamp.replace(tzinfo=None) < previous.event_timestamp.replace(tzinfo=None):
            previous.event_timestamp = timestamp
            previous.source_filename = filename
    pending_points = set(pending) - existing_points
    for decision in decisions:
        decision.device_event_missing = missing_event_for_marked_device(
            decision.device_highlighted, decision.address, pending_points, existing_points)
    pending_matches = [{"point": point, "timestamp": format_event_date(pending[point].event_timestamp)} for point in sorted(pending_points & allowed_points)]
    device_statuses = [{"id": item.id, "device_highlighted": bool(item.device_highlighted),
                        "device_event_missing": bool(item.device_event_missing)} for item in decisions]
    return pending_matches, device_statuses, existing_points


def register_event_routes(router, store) -> None:
    @router.post("/{inspection_id}/event-history")
    async def add_event_history(
        inspection_id: str,
        request: Request,
        point_list_id: str = Form(...),
        review_required: bool = Form(False),
        event_file: UploadFile = File(...),
    ) -> dict:
        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            point_list = (
                session.query(PointList)
                .filter(PointList.inspection_id == inspection_id, PointList.id == point_list_id, PointList.deleted_at.is_(None))
                .first()
            )
            if point_list is None:
                return {"error": "Selected Points List was not found for this inspection."}

        target = ensure_inspection_upload_dir(inspection_id)

        filename = Path(event_file.filename or "event-history.bin").name
        if not filename.lower().endswith(".xlsx"):
            return {"error": "Event History processing currently supports XLSX files."}
        destination = target / f"{uuid4().hex}-{filename}"
        destination.write_bytes(await event_file.read())
        try:
            extracted = parse_event_history_xlsx(destination)
        except ValueError as exc:
            destination.unlink(missing_ok=True)
            return {"error": f"{filename}: {exc}"}

        with store.begin() as session:
            # Serialize simultaneous evidence uploads for the same panel.
            panel = session.query(PointList).filter_by(id=point_list_id, inspection_id=inspection_id).with_for_update().one()
            if panel.deleted_at is not None:
                raise HTTPException(status_code=404, detail="Points List not found.")
            if review_required:
                upload_id = str(uuid4())
                session.add(SourceFile(id=upload_id, inspection_id=inspection_id, filename=filename,
                    path=str(destination), kind="er:" + point_list_id.replace("-", "")))
                allowed = {row.address for row in session.query(PointListDecision).filter_by(
                    inspection_id=inspection_id, point_list_id=point_list_id, accepted=True, deleted=False)}
                record_decision(session, request, inspection_id, point_list_id, "event_upload_review_requested",
                    {"upload_id": upload_id, "filename": filename, "matches": extracted})
                return {"status": "review_required", "upload_id": upload_id, "filename": filename,
                    "point_list_id": point_list_id, "matched_points": len(allowed & extracted.keys()),
                    "accepted_times": session.query(PointListEventDate).filter_by(
                        inspection_id=inspection_id, point_list_id=point_list_id).count(),
                    "pending_times": session.query(PointListPendingEventDate).filter_by(
                        inspection_id=inspection_id, point_list_id=point_list_id).count()}
            pending_matches, device_statuses, existing_points = _merge_events(
                session, inspection_id, point_list_id, extracted, filename)
            session.add(SourceFile(id=str(uuid4()), inspection_id=inspection_id, filename=filename,
                                   path=str(destination), kind=event_history_kind(point_list_id)))
        return {
            "inspection_id": inspection_id,
            "point_list_id": point_list_id,
            "filename": filename,
            "status": "matched",
            "matched_points": len(extracted),
            "pending_matches": pending_matches,
            "device_statuses": device_statuses,
            "ignored_existing": sum(point in existing_points for point in extracted),
        }

    @router.post("/{inspection_id}/event-history/{upload_id}/review")
    def review_event_history(inspection_id: str, upload_id: str, request: Request, payload: dict = Body(...)):
        action = payload.get("action")
        point_list_id = str(payload.get("point_list_id") or "")
        if action not in {"keep", "clear", "reject"}:
            raise HTTPException(status_code=400, detail="Choose keep, clear, or reject.")
        if action == "clear" and payload.get("confirmed") is not True:
            raise HTTPException(status_code=400, detail="Confirm clearing this Points List's accepted and pending times.")
        with store.begin() as session:
            panel = session.query(PointList).filter_by(id=point_list_id, inspection_id=inspection_id).with_for_update().first()
            if panel is None or panel.deleted_at is not None:
                raise HTTPException(status_code=404, detail="Points List not found.")
            source = session.query(SourceFile).filter_by(id=upload_id, inspection_id=inspection_id).with_for_update().first()
            if source is None or source.kind != "er:" + point_list_id.replace("-", ""):
                raise HTTPException(status_code=409, detail="This upload is no longer awaiting review for this Points List.")
            if action == "reject":
                source.kind = "ex:" + point_list_id.replace("-", "")
                record_decision(session, request, inspection_id, point_list_id, "event_upload_rejected",
                    {"upload_id": upload_id, "filename": source.filename})
                return {"status": "rejected"}
            extracted = parse_event_history_xlsx(Path(source.path))
            if action == "clear":
                previous = []
                for model, state in ((PointListEventDate, "accepted"), (PointListPendingEventDate, "pending")):
                    rows = session.query(model).filter_by(inspection_id=inspection_id, point_list_id=point_list_id)
                    previous.extend({"point": row.point_address, "timestamp": row.event_timestamp,
                        "source_filename": row.source_filename, "state": state} for row in rows.all())
                    rows.delete(synchronize_session=False)
                record_decision(session, request, inspection_id, point_list_id, "event_results_cleared",
                    {"upload_id": upload_id, "previous": previous})
            matches, statuses, existing = _merge_events(session, inspection_id, point_list_id, extracted, source.filename)
            source.kind = event_history_kind(point_list_id)
            record_decision(session, request, inspection_id, point_list_id, "event_upload_applied",
                {"upload_id": upload_id, "action": action, "filename": source.filename})
            return {"status": "matched", "pending_matches": matches, "device_statuses": statuses}

    @router.post("/{inspection_id}/event-dates/save")
    def save_event_dates(inspection_id: str, request: Request, payload: dict = Body(default={})) -> dict:
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
                .filter(PointList.inspection_id == inspection_id, PointList.id == point_list_id, PointList.deleted_at.is_(None))
                .with_for_update().first()
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

            for item in matches:
                if not isinstance(item, dict):
                    ignored_invalid += 1
                    continue
                point = normalize_point(item.get("point"))
                timestamp = parse_saved_timestamp(item.get("timestamp"))
                source_filename = str(item.get("source_filename") or "")

                if point is None or timestamp is None or point not in allowed_points:
                    ignored_invalid += 1
                    continue
                if point in existing_points:
                    ignored_existing += 1
                    continue

                pending = session.get(PointListPendingEventDate, (inspection_id, point_list_id, point))
                if pending and timestamp.replace(tzinfo=None) == pending.event_timestamp.replace(tzinfo=None):
                    source_filename = pending.source_filename
                else:
                    source_filename = "manual_event_acceptance"
                record_decision(session, request, inspection_id, point_list_id, "event_accepted",
                                {"point": point, "timestamp": timestamp, "source_filename": source_filename})

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
                session.query(PointListPendingEventDate).filter_by(inspection_id=inspection_id, point_list_id=point_list_id, point_address=point).delete(synchronize_session=False)
                for decision in accepted_points:
                    if decision.address == point:
                        decision.device_event_missing = False
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

    @router.post("/{inspection_id}/event-dates/clear")
    def clear_event_dates(inspection_id: str, request: Request, payload: dict = Body(default={})) -> dict:
        point_list_id = str(payload.get("point_list_id") or "").strip()
        if not point_list_id:
            return {"error": "point_list_id is required"}
        if payload.get("confirmed") is not True:
            raise HTTPException(status_code=400, detail="Explicit confirmation is required to clear accepted test results.")
        with store.begin() as session:
            panel = session.query(PointList).filter(
                PointList.id == point_list_id, PointList.inspection_id == inspection_id,
                PointList.deleted_at.is_(None),
            ).with_for_update().first()
            if panel is None:
                raise HTTPException(status_code=404, detail="Points List not found.")
            previous = session.query(PointListEventDate).filter_by(
                inspection_id=inspection_id, point_list_id=point_list_id,
            ).all()
            record_decision(session, request, inspection_id, point_list_id, "event_results_cleared", [
                {"id": item.id, "point": item.point_address, "timestamp": item.event_timestamp,
                 "source_filename": item.source_filename} for item in previous
            ])
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
