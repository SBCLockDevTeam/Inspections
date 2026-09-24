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
    event_history_kind,
    format_event_date,
    parse_date_value,
)
from alarm_inspection.api.routers.inspections_deps import (
    find_inspection_identity_conflict,
)
from alarm_inspection.api.routers.inspections_events import register_event_routes
from alarm_inspection.api.routers.inspections_export import register_export_routes
from alarm_inspection.api.routers.inspections_nfpa_draft import register_nfpa_draft_routes
from alarm_inspection.api.routers.inspections_points_workflow import register_point_workflow_routes
from alarm_inspection.api.routers.inspections_templates import register_template_routes
from alarm_inspection.storage import (
    Inspection,
    PointList,
    PointListDecision,
    PointListEventDate,
    SourceFile,
)


def create_router(store) -> APIRouter:
    router = APIRouter(prefix="/api/inspections", tags=["inspections"])

    @router.post("/blank")
    def create_blank_inspection() -> dict:
        inspection_id = str(uuid4())
        created_at = datetime.now(timezone.utc)
        inferred_date = date.today()
        with store.begin() as session:
            session.add(
                Inspection(
                    id=inspection_id,
                    store_number="",
                    address="",
                    store_type="Walmart - Supercenter",
                    inspector_name="",
                    start_date=inferred_date,
                    completion_date=inferred_date,
                    status="pending_event_history",
                    created_at=created_at,
                )
            )
        return {"id": inspection_id, "status": "pending_event_history"}

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
            duplicate_id = find_inspection_identity_conflict(
                session,
                "Walmart - Supercenter",
                store_number,
                inferred_date,
            )
            if duplicate_id:
                return {
                    "error": (
                        f"Inspection already exists for Walmart - Supercenter / {store_number.strip()} "
                        f"on {inferred_date.isoformat()}."
                    )
                }
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
                            location=str(decision.get("location") or ""),
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
                        "id": point.id,
                        "address": point.address,
                        "text": point.text,
                        "location": point.location,
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

            candidate_store_number = store_number or inspection.store_number
            candidate_store_type = store_type or inspection.store_type
            candidate_start_date = start_date or inspection.start_date
            duplicate_id = find_inspection_identity_conflict(
                session,
                candidate_store_type,
                candidate_store_number,
                candidate_start_date,
                exclude_inspection_id=inspection.id,
            )
            if duplicate_id:
                return {
                    "error": (
                        f"Inspection already exists for {candidate_store_type} / {candidate_store_number} "
                        f"on {candidate_start_date.isoformat()}."
                    )
                }

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

    register_point_workflow_routes(router, store)
    register_event_routes(router, store)
    register_export_routes(router, store)
    register_nfpa_draft_routes(router, store)
    register_template_routes(router, store)

    return router
