from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Body, File, Form, UploadFile

from alarm_inspection.api.common import as_bool, ensure_inspection_upload_dir, parse_saved_timestamp
from alarm_inspection.domain.points import normalize_point
from alarm_inspection.storage import (
    Inspection,
    PointList,
    PointListDecision,
    PointListEventDate,
    SourceFile,
)


def register_point_workflow_routes(router, store) -> None:
    @router.post("/{inspection_id}/point-lists")
    async def add_point_list_to_inspection(
        inspection_id: str,
        point_list_category: str = Form(...),
        points_file: UploadFile = File(...),
        point_decisions: str = Form("[]"),
    ) -> dict:
        filename = Path(points_file.filename or "points.xlsx").name
        if not filename.lower().endswith(".xlsx"):
            return {"error": "The first parser supports XLSX files; PDF and legacy XLS need a separate adapter."}

        try:
            decisions_to_store = json.loads(point_decisions)
        except json.JSONDecodeError:
            decisions_to_store = []

        if not isinstance(decisions_to_store, list) or not decisions_to_store:
            return {"error": "Review decisions are required before adding a Points List."}
        if any(
            as_bool(item.get("accepted"), default=False) is False and as_bool(item.get("deleted"), default=False) is False
            for item in decisions_to_store
        ):
            return {"error": "All Review rows must be accepted or deleted before finishing the review."}

        content = await points_file.read()
        if not content:
            return {"error": "Uploaded Points List file was empty."}

        with store.begin() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            target_dir = ensure_inspection_upload_dir(inspection_id)
            stamped = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            stored_name = f"{stamped}-{filename}"
            destination = target_dir / stored_name
            destination.write_bytes(content)

            session.add(
                SourceFile(
                    id=str(uuid4()),
                    inspection_id=inspection_id,
                    filename=stored_name,
                    path=str(destination),
                    kind="points_list",
                )
            )

            point_list_id = str(uuid4())
            now = datetime.now(timezone.utc)
            session.add(
                PointList(
                    id=point_list_id,
                    inspection_id=inspection_id,
                    category=point_list_category,
                    filename=stored_name,
                    path=str(destination),
                    accepted_at=now,
                )
            )

            for decision in decisions_to_store:
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
            "inspection_id": inspection_id,
            "point_list_id": point_list_id,
            "filename": stored_name,
            "accepted_points": sum(1 for d in decisions_to_store if as_bool(d.get("accepted"), default=False)),
            "status": "saved",
        }

    @router.delete("/{inspection_id}/point-lists/{point_list_id}")
    def delete_point_list_from_inspection(inspection_id: str, point_list_id: str) -> dict:
        file_to_remove: Path | None = None
        with store.begin() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            point_list = (
                session.query(PointList)
                .filter(PointList.inspection_id == inspection_id, PointList.id == point_list_id)
                .first()
            )
            if point_list is None:
                return {"error": "point list not found"}

            file_to_remove = Path(point_list.path) if point_list.path else None

            session.query(PointListEventDate).filter(
                PointListEventDate.inspection_id == inspection_id,
                PointListEventDate.point_list_id == point_list_id,
            ).delete(synchronize_session=False)
            session.query(PointListDecision).filter(
                PointListDecision.inspection_id == inspection_id,
                PointListDecision.point_list_id == point_list_id,
            ).delete(synchronize_session=False)
            session.query(SourceFile).filter(
                SourceFile.inspection_id == inspection_id,
                SourceFile.kind == "points_list",
                SourceFile.filename == point_list.filename,
            ).delete(synchronize_session=False)
            session.delete(point_list)

        if file_to_remove is not None and file_to_remove.exists() and file_to_remove.is_file():
            file_to_remove.unlink(missing_ok=True)

        return {"inspection_id": inspection_id, "point_list_id": point_list_id, "status": "deleted"}

    @router.post("/{inspection_id}/accepted-points/save")
    def save_accepted_points(inspection_id: str, payload: dict = Body(default={})) -> dict:
        point_list_id = str(payload.get("point_list_id") or "").strip()
        rows = payload.get("rows", [])
        if not point_list_id:
            return {"error": "point_list_id is required"}
        if not isinstance(rows, list):
            return {"error": "rows must be a list"}

        updated_rows = 0
        saved_event_dates = 0
        ignored_rows = 0

        with store.begin() as session:
            point_list = (
                session.query(PointList)
                .filter(PointList.inspection_id == inspection_id, PointList.id == point_list_id)
                .first()
            )
            if point_list is None:
                return {"error": "Selected Points List was not found for this inspection."}

            decisions = (
                session.query(PointListDecision)
                .filter(
                    PointListDecision.inspection_id == inspection_id,
                    PointListDecision.point_list_id == point_list_id,
                    PointListDecision.accepted.is_(True),
                    PointListDecision.deleted.is_(False),
                )
                .all()
            )
            decisions_by_id = {item.id: item for item in decisions}

            # Explicit technician save replaces current event-date table for this points list.
            session.query(PointListEventDate).filter(
                PointListEventDate.inspection_id == inspection_id,
                PointListEventDate.point_list_id == point_list_id,
            ).delete(synchronize_session=False)

            for row in rows:
                if not isinstance(row, dict):
                    ignored_rows += 1
                    continue

                decision_id = str(row.get("id") or "").strip()
                decision = decisions_by_id.get(decision_id)
                if decision is None:
                    ignored_rows += 1
                    continue

                normalized_address = normalize_point(row.get("address"))
                decision.address = normalized_address
                decision.text = str(row.get("text") or "").strip()
                decision.location = str(row.get("location") or "").strip()
                updated_rows += 1

                if normalized_address is None:
                    continue
                timestamp = parse_saved_timestamp(row.get("event_date"))
                if timestamp is None:
                    continue

                session.add(
                    PointListEventDate(
                        id=str(uuid4()),
                        inspection_id=inspection_id,
                        point_list_id=point_list_id,
                        point_address=normalized_address,
                        event_timestamp=timestamp,
                        source_filename="accepted_points_table",
                    )
                )
                saved_event_dates += 1

        return {
            "inspection_id": inspection_id,
            "point_list_id": point_list_id,
            "status": "saved",
            "updated_rows": updated_rows,
            "saved_event_dates": saved_event_dates,
            "ignored_rows": ignored_rows,
        }
