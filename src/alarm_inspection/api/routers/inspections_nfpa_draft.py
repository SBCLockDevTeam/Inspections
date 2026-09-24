from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

from fastapi import Body, HTTPException
from fastapi.responses import StreamingResponse

from alarm_inspection.api.common import ensure_inspection_upload_dir
from alarm_inspection.api.pdf_export import (
    build_default_nfpa_draft,
    build_nfpa_draft_filename,
    normalize_nfpa_draft_fields,
    parse_nfpa_draft_fields,
    render_nfpa_draft_pdf,
    serialize_nfpa_draft_fields,
)
from alarm_inspection.storage import Inspection, InspectionPdfDraft, SourceFile


def register_nfpa_draft_routes(router, store) -> None:
    @router.get("/{inspection_id}/nfpa-draft")
    def get_nfpa_draft(inspection_id: str) -> dict:
        with store.begin() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            defaults = build_default_nfpa_draft(
                store_number=inspection.store_number,
                address=inspection.address,
                inspector_name=inspection.inspector_name,
            )
            draft = session.get(InspectionPdfDraft, inspection_id)
            if draft is None:
                fields = defaults
                draft = InspectionPdfDraft(
                    inspection_id=inspection_id,
                    fields_json=serialize_nfpa_draft_fields(fields),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(draft)
            else:
                fields = parse_nfpa_draft_fields(draft.fields_json, defaults)
                draft.fields_json = serialize_nfpa_draft_fields(fields)

            return {
                "inspection_id": inspection_id,
                "fields": fields,
                "updated_at": draft.updated_at.isoformat() if draft.updated_at else "",
            }

    @router.put("/{inspection_id}/nfpa-draft")
    def save_nfpa_draft(inspection_id: str, payload: dict = Body(default={})) -> dict:
        with store.begin() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            defaults = build_default_nfpa_draft(
                store_number=inspection.store_number,
                address=inspection.address,
                inspector_name=inspection.inspector_name,
            )
            fields = normalize_nfpa_draft_fields(payload.get("fields"), defaults)
            draft = session.get(InspectionPdfDraft, inspection_id)
            now = datetime.now(timezone.utc)
            if draft is None:
                draft = InspectionPdfDraft(
                    inspection_id=inspection_id,
                    fields_json=serialize_nfpa_draft_fields(fields),
                    updated_at=now,
                )
                session.add(draft)
            else:
                draft.fields_json = serialize_nfpa_draft_fields(fields)
                draft.updated_at = now

            return {
                "inspection_id": inspection_id,
                "fields": fields,
                "updated_at": now.isoformat(),
                "status": "saved",
            }

    @router.post("/{inspection_id}/nfpa-draft/download")
    def download_nfpa_draft_pdf(inspection_id: str):
        with store.begin() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                raise HTTPException(status_code=404, detail="inspection not found")

            defaults = build_default_nfpa_draft(
                store_number=inspection.store_number,
                address=inspection.address,
                inspector_name=inspection.inspector_name,
            )
            draft = session.get(InspectionPdfDraft, inspection_id)
            if draft is None:
                fields = defaults
                now = datetime.now(timezone.utc)
                draft = InspectionPdfDraft(
                    inspection_id=inspection_id,
                    fields_json=serialize_nfpa_draft_fields(fields),
                    updated_at=now,
                )
                session.add(draft)
            else:
                fields = parse_nfpa_draft_fields(draft.fields_json, defaults)

            draft.updated_at = datetime.now(timezone.utc)

            try:
                pdf_bytes = render_nfpa_draft_pdf(
                    inspection_id=inspection_id,
                    fields=fields,
                    completion_date=inspection.completion_date,
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc

            filename = build_nfpa_draft_filename(
                inspection.store_number,
                inspection.address,
                inspection.completion_date,
            )
            export_dir = ensure_inspection_upload_dir(inspection_id)
            export_path = export_dir / filename
            export_path.write_bytes(pdf_bytes)
            session.add(
                SourceFile(
                    id=str(uuid4()),
                    inspection_id=inspection_id,
                    filename=filename,
                    path=str(export_path),
                    kind="nfpa_draft_pdf",
                )
            )

        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)
