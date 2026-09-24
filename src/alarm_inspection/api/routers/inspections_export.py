from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from fastapi import Body, HTTPException
from fastapi.responses import StreamingResponse

from alarm_inspection.api.common import ensure_inspection_upload_dir, format_event_date
from alarm_inspection.api.pdf_export import (
    build_report_filename,
    normalize_export_rows,
    render_report_pdf,
    validate_export_rows,
)
from alarm_inspection.storage import Inspection, PointList, PointListDecision, PointListEventDate, SourceFile


def register_export_routes(router, store) -> None:
    @router.post("/{inspection_id}/export-pdf")
    def export_pdf(inspection_id: str, payload: dict = Body(default={})):
        point_list_id = str(payload.get("point_list_id") or "").strip()
        if not point_list_id:
            raise HTTPException(status_code=400, detail="point_list_id is required")

        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                raise HTTPException(status_code=404, detail="inspection not found")

            point_list = (
                session.query(PointList)
                .filter(PointList.inspection_id == inspection_id, PointList.id == point_list_id)
                .first()
            )
            if point_list is None:
                raise HTTPException(status_code=404, detail="Selected Points List was not found for this inspection.")

            accepted_points = (
                session.query(PointListDecision)
                .filter(
                    PointListDecision.inspection_id == inspection_id,
                    PointListDecision.point_list_id == point_list_id,
                    PointListDecision.accepted.is_(True),
                    PointListDecision.deleted.is_(False),
                )
                .order_by(PointListDecision.address.asc(), PointListDecision.text.asc())
                .all()
            )
            saved_event_dates = (
                session.query(PointListEventDate)
                .filter(
                    PointListEventDate.inspection_id == inspection_id,
                    PointListEventDate.point_list_id == point_list_id,
                )
                .all()
            )

        mapped_dates = {item.point_address: item.event_timestamp for item in saved_event_dates}
        rows = normalize_export_rows(payload.get("rows"))
        if not rows:
            rows = [
                {
                    "text": point.text,
                    "address": "" if point.address is None else str(point.address),
                    "location": point.location,
                    "event_date": (
                        format_event_date(mapped_dates.get(point.address)) if point.address in mapped_dates else ""
                    )
                    or "",
                }
                for point in accepted_points
            ]

        validation_error = validate_export_rows(rows)
        if validation_error:
            raise HTTPException(status_code=400, detail=validation_error)

        try:
            pdf_bytes = render_report_pdf(
                inspection_id=inspection.id,
                store_number=inspection.store_number,
                store_type=inspection.store_type,
                address=inspection.address,
                inspector_name=inspection.inspector_name,
                category=point_list.category,
                start_date=inspection.start_date,
                completion_date=inspection.completion_date,
                rows=rows,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        filename = build_report_filename(
            inspection.store_number,
            inspection.address,
            point_list.category,
            inspection.completion_date,
        )
        export_dir = ensure_inspection_upload_dir(inspection_id)
        export_path = export_dir / filename
        export_path.write_bytes(pdf_bytes)

        with store.begin() as session:
            session.add(
                SourceFile(
                    id=str(uuid4()),
                    inspection_id=inspection_id,
                    filename=filename,
                    path=str(export_path),
                    kind=f"report_pdf:{point_list_id[:12]}",
                )
            )

        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)
