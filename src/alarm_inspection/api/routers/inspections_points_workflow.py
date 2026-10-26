from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Body, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, StrictBool

from alarm_inspection.api.audit import record_decision
from alarm_inspection.api.common import as_bool, ensure_inspection_upload_dir, parse_saved_timestamp
from alarm_inspection.domain.points import normalize_point
from alarm_inspection.api.panel_types import resolve_panel_type
from alarm_inspection.storage import (
    Inspection,
    PointList,
    PointListDecision,
    PointListEventDate,
    PointListPendingEventDate,
    SourceFile,
)


class DeviceHighlightUpdate(BaseModel):
    highlighted: StrictBool


def register_point_workflow_routes(router, store) -> None:
    @router.patch("/{inspection_id}/point-lists/{point_list_id}/points/{point_id}/highlight")
    def highlight_device(inspection_id: str, point_list_id: str, point_id: str, payload: DeviceHighlightUpdate) -> dict:
        with store.begin() as session:
            inspection = session.get(Inspection, inspection_id)
            point_list = session.get(PointList, point_list_id)
            point = session.get(PointListDecision, point_id)
            if (inspection is None or inspection.status == "deleted"
                    or point_list is None or point_list.deleted_at is not None or point_list.inspection_id != inspection_id
                    or point is None or point.inspection_id != inspection_id
                    or point.point_list_id != point_list_id or not point.accepted or point.deleted):
                raise HTTPException(status_code=404, detail="Accepted point not found.")
            point.device_highlighted = payload.highlighted
            point.device_event_missing = False
        return {"id": point_id, "device_highlighted": payload.highlighted}

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

            try:
                point_list_category = resolve_panel_type(session, point_list_category)
            except ValueError as exc:
                return {"error": str(exc)}
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
    def delete_point_list_from_inspection(inspection_id: str, point_list_id: str, request: Request) -> dict:
        with store.begin() as session:
            point_list = session.query(PointList).filter(
                PointList.inspection_id == inspection_id, PointList.id == point_list_id,
                PointList.deleted_at.is_(None),
            ).with_for_update().first()
            if point_list is None:
                raise HTTPException(status_code=404, detail="Points List not found.")
            point_list.deleted_at = datetime.now(timezone.utc)
            point_list.deleted_by = request.state.current_user.id
            record_decision(session, request, inspection_id, point_list_id, "panel_deleted",
                            {"filename": point_list.filename, "category": point_list.category})

        return {"inspection_id": inspection_id, "point_list_id": point_list_id, "status": "deleted"}

    @router.post("/{inspection_id}/accepted-points/save")
    def save_accepted_points(inspection_id: str, request: Request, payload: dict = Body(default={})) -> dict:
        point_list_id = str(payload.get("point_list_id") or "").strip()
        rows = payload.get("rows", [])
        if not point_list_id or not isinstance(rows, list):
            raise HTTPException(status_code=400, detail="point_list_id and a rows list are required.")
        updated_rows = saved_event_dates = ignored_rows = 0
        with store.begin() as session:
            panel = session.query(PointList).filter(
                PointList.inspection_id == inspection_id, PointList.id == point_list_id,
                PointList.deleted_at.is_(None),
            ).with_for_update().first()
            if panel is None:
                raise HTTPException(status_code=404, detail="Selected Points List was not found for this inspection.")
            decisions = session.query(PointListDecision).filter_by(
                inspection_id=inspection_id, point_list_id=point_list_id, accepted=True, deleted=False,
            ).all()
            decisions_by_id = {item.id: item for item in decisions}
            mappings = {item.point_address: item for item in session.query(PointListEventDate).filter_by(
                inspection_id=inspection_id, point_list_id=point_list_id,
            ).all()}
            for row in rows:
                if not isinstance(row, dict) or row.get("id") not in decisions_by_id:
                    ignored_rows += 1
                    continue
                decision = decisions_by_id[row["id"]]
                before = {"address": decision.address, "text": decision.text, "location": decision.location}
                address = normalize_point(row.get("address", decision.address))
                if address is None or not 1 <= address <= 255:
                    raise HTTPException(status_code=400, detail="Point addresses must be between 1 and 255.")
                if address != decision.address and decision.address in mappings:
                    raise HTTPException(status_code=409, detail="Clear accepted test results explicitly before changing a mapped point address.")
                decision.address = address
                if "text" in row:
                    decision.text = str(row["text"] or "").strip()
                if "location" in row:
                    decision.location = str(row["location"] or "").strip()
                after = {"address": decision.address, "text": decision.text, "location": decision.location}
                if before != after:
                    record_decision(session, request, inspection_id, point_list_id, "point_edited",
                                    {"point_id": decision.id, "before": before, "after": after})
                updated_rows += 1
                raw_timestamp = str(row.get("event_date") or "").strip()
                # Empty/stale fields never clear accepted mappings during an ordinary save.
                if not raw_timestamp:
                    continue
                timestamp = parse_saved_timestamp(raw_timestamp)
                if timestamp is None:
                    raise HTTPException(status_code=400, detail=f"Point {address}: invalid test timestamp.")
                existing = mappings.get(address)
                if existing is not None:
                    if timestamp.replace(tzinfo=None) != existing.event_timestamp.replace(tzinfo=None):
                        raise HTTPException(status_code=409, detail=f"Point {address}: accepted test results changed. Reload, or explicitly clear results before correcting them.")
                    continue
                mapping = PointListEventDate(
                    id=str(uuid4()), inspection_id=inspection_id, point_list_id=point_list_id,
                    point_address=address, event_timestamp=timestamp, source_filename="accepted_points_table",
                )
                session.add(mapping)
                mappings[address] = mapping
                record_decision(session, request, inspection_id, point_list_id, "manual_event_accepted",
                                {"point": address, "timestamp": timestamp, "source_filename": mapping.source_filename})
                session.query(PointListPendingEventDate).filter_by(
                    inspection_id=inspection_id, point_list_id=point_list_id, point_address=address,
                ).delete(synchronize_session=False)
                decision.device_event_missing = False
                saved_event_dates += 1
            addresses = [item.address for item in decisions if item.address is not None]
            if len(set(addresses)) != len(addresses):
                raise HTTPException(status_code=400, detail="Duplicate point addresses require correction before saving.")
        return {"inspection_id": inspection_id, "point_list_id": point_list_id, "status": "saved",
                "updated_rows": updated_rows, "saved_event_dates": saved_event_dates, "ignored_rows": ignored_rows}
