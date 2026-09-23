from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import shutil
from uuid import uuid4

from fastapi import APIRouter, Body, File, Form, Query, UploadFile

from alarm_inspection.api.common import (
    UPLOAD_ROOT,
    as_bool,
    ensure_inspection_upload_dir,
    event_history_kind,
    format_event_date,
    parse_date_value,
    parse_saved_timestamp,
)
from alarm_inspection.domain.points import normalize_point
from alarm_inspection.intake.event_history import parse_xlsx as parse_event_history_xlsx
from alarm_inspection.storage import (
    Inspection,
    PointList,
    PointListDecision,
    PointListEventDate,
    SourceFile,
)


def create_router(store) -> APIRouter:
    router = APIRouter(prefix="/api/inspections", tags=["inspections"])

    @router.post("")
    async def create_inspection(
        store_number: str = Form(...),
        address: str = Form(...),
        point_list_categories: list[str] = Form(...),
        points_files: list[UploadFile] = File(...),
        point_decisions: str = Form("[]"),
    ) -> dict:
        inspection_id = str(uuid4())
        target = UPLOAD_ROOT / inspection_id
        target.mkdir(parents=True, exist_ok=True)
        files: list[str] = []
        point_file_names: list[str] = []
        for upload in points_files:
            filename = Path(upload.filename or "upload.bin").name
            destination = target / filename
            destination.write_bytes(await upload.read())
            files.append(filename)
            point_file_names.append(filename)
        created_at = datetime.now(timezone.utc)
        inferred_date = date.today()

        decisions_to_store = json.loads(point_decisions)
        if not isinstance(decisions_to_store, list) or not decisions_to_store:
            return {"error": "Review decisions are required before creating an inspection."}
        if any(
            as_bool(item.get("accepted"), default=False) is False and as_bool(item.get("deleted"), default=False) is False
            for item in decisions_to_store
        ):
            return {"error": "All Review rows must be accepted or deleted before finishing the review."}

        with store.begin() as session:
            session.add(
                Inspection(
                    id=inspection_id,
                    store_number=store_number,
                    address=address,
                    store_type="Walmart - Supercenter",
                    inspector_name="",
                    start_date=inferred_date,
                    completion_date=inferred_date,
                    status="pending_event_history",
                    created_at=created_at,
                )
            )
            for filename in files:
                session.add(
                    SourceFile(
                        id=str(uuid4()),
                        inspection_id=inspection_id,
                        filename=filename,
                        path=str(target / filename),
                        kind="points_list",
                    )
                )
            point_list_ids_by_filename: dict[str, str] = {}
            for filename, list_category in zip(point_file_names, point_list_categories, strict=False):
                point_list_id = str(uuid4())
                session.add(
                    PointList(
                        id=point_list_id,
                        inspection_id=inspection_id,
                        category=list_category,
                        filename=filename,
                        path=str(target / filename),
                        accepted_at=created_at,
                    )
                )
                point_list_ids_by_filename[filename] = point_list_id

            default_list_id = point_list_ids_by_filename.get(point_file_names[0], "") if point_file_names else ""
            for decision in decisions_to_store:
                source_filename = str(decision.get("source_filename") or "")
                point_list_id = point_list_ids_by_filename.get(source_filename, default_list_id)
                if point_list_id:
                    session.add(
                        PointListDecision(
                            id=str(uuid4()),
                            inspection_id=inspection_id,
                            point_list_id=point_list_id,
                            address=decision.get("address"),
                            text=decision.get("text", ""),
                            accepted=as_bool(decision.get("accepted"), default=False),
                            deleted=as_bool(decision.get("deleted"), default=False),
                            reason=decision.get("reason", "technician review"),
                        )
                    )
        return {
            "id": inspection_id,
            "status": "pending_event_history",
            "files": files,
            "accepted_points": sum(1 for d in decisions_to_store if as_bool(d.get("accepted"), default=False)),
        }

    @router.get("")
    def list_inspections() -> list[dict]:
        with store() as session:
            rows = session.query(Inspection).order_by(Inspection.created_at.desc()).all()
            return [
                {
                    "id": row.id,
                    "store_number": row.store_number,
                    "address": row.address,
                    "start_date": row.start_date.isoformat(),
                    "completion_date": row.completion_date.isoformat(),
                    "status": row.status,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]

    @router.delete("/{inspection_id}")
    def delete_inspection(inspection_id: str) -> dict:
        upload_path = UPLOAD_ROOT / inspection_id
        with store.begin() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            session.query(PointListEventDate).filter(PointListEventDate.inspection_id == inspection_id).delete(
                synchronize_session=False
            )
            session.query(PointListDecision).filter(PointListDecision.inspection_id == inspection_id).delete(
                synchronize_session=False
            )
            session.query(PointList).filter(PointList.inspection_id == inspection_id).delete(synchronize_session=False)
            session.query(SourceFile).filter(SourceFile.inspection_id == inspection_id).delete(synchronize_session=False)
            session.delete(inspection)

        shutil.rmtree(upload_path, ignore_errors=True)
        return {"id": inspection_id, "status": "deleted"}

    @router.get("/{inspection_id}")
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

            selected_kind = event_history_kind(selected_point_list_id)
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
                "store_type": inspection.store_type,
                "address": inspection.address,
                "inspector_name": inspection.inspector_name,
                "start_date": inspection.start_date.isoformat(),
                "completion_date": inspection.completion_date.isoformat(),
                "status": inspection.status,
                "accepted_points": [
                    {
                        "address": point.address,
                        "text": point.text,
                        "event_date": format_event_date(
                            mapped_dates.get(point.address) if point.address is not None else None
                        ),
                    }
                    for point in scoped_points
                ],
                "point_lists": [
                    {"id": item.id, "category": item.category, "filename": item.filename} for item in point_lists
                ],
                "selected_point_list_id": selected_point_list_id,
                "event_history_files": [file.filename for file in event_history_files],
            }

    @router.patch("/{inspection_id}")
    def update_inspection_details(inspection_id: str, payload: dict = Body(default={})) -> dict:
        with store.begin() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            store_number = str(payload.get("store_number") or "").strip()
            store_type = str(payload.get("store_type") or "").strip()
            address = str(payload.get("address") or "").strip()
            inspector_name = str(payload.get("inspector_name") or "").strip()
            start_date = parse_date_value(payload.get("start_date"))
            completion_date = parse_date_value(payload.get("completion_date"))

            if store_number:
                inspection.store_number = store_number
            if store_type:
                inspection.store_type = store_type
            if address:
                inspection.address = address
            inspection.inspector_name = inspector_name
            if start_date is not None:
                inspection.start_date = start_date
            if completion_date is not None:
                inspection.completion_date = completion_date

            return {
                "id": inspection.id,
                "store_number": inspection.store_number,
                "store_type": inspection.store_type,
                "address": inspection.address,
                "inspector_name": inspection.inspector_name,
                "start_date": inspection.start_date.isoformat(),
                "completion_date": inspection.completion_date.isoformat(),
                "status": inspection.status,
            }

    @router.post("/{inspection_id}/event-history")
    async def add_event_history(
        inspection_id: str,
        point_list_id: str = Form(...),
        event_file: UploadFile = File(...),
    ) -> dict:
        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            point_list = (
                session.query(PointList)
                .filter(PointList.inspection_id == inspection_id, PointList.id == point_list_id)
                .first()
            )
            if point_list is None:
                return {"error": "Selected Points List was not found for this inspection."}

        target = ensure_inspection_upload_dir(inspection_id)

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
            {"point": point, "timestamp": format_event_date(timestamp)}
            for point, timestamp in sorted(extracted.items())
            if point not in existing_points
        ]

        with store.begin() as session:
            session.add(
                SourceFile(
                    id=str(uuid4()),
                    inspection_id=inspection_id,
                    filename=filename,
                    path=str(destination),
                    kind=event_history_kind(point_list_id),
                )
            )
        return {
            "inspection_id": inspection_id,
            "point_list_id": point_list_id,
            "filename": filename,
            "status": "matched",
            "matched_points": len(extracted),
            "pending_matches": pending_matches,
            "ignored_existing": len(extracted) - len(pending_matches),
        }

    @router.post("/{inspection_id}/event-dates/save")
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

    @router.post("/{inspection_id}/event-dates/clear")
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

    return router
