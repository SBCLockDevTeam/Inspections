from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import Body, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from alarm_inspection.api.common import ensure_inspection_upload_dir
from alarm_inspection.api.pdf_templates import (
    default_template_download_name,
    extract_template_fields,
    fill_template_pdf,
    list_templates,
    normalize_template_field_values,
    resolve_template_path,
    template_meta,
)
from alarm_inspection.api.routers.inspections_deps import (
    latest_saved_nfpa_pdf_path,
    load_template_draft_values,
    resolve_official_nfpa_template_path,
)
from alarm_inspection.storage import Inspection, InspectionPdfTemplateDraft, SourceFile


def register_template_routes(router, store) -> None:
    @router.get("/{inspection_id}/nfpa-template/status")
    def get_nfpa_template_status(inspection_id: str) -> dict:
        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}
            saved_path, saved_filename = latest_saved_nfpa_pdf_path(session, inspection_id)

        template_path = resolve_official_nfpa_template_path()
        return {
            "inspection_id": inspection_id,
            "has_official_template": bool(template_path),
            "official_template_filename": template_path.name if template_path else "",
            "has_saved_copy": bool(saved_path),
            "saved_copy_filename": saved_filename,
        }

    @router.post("/{inspection_id}/nfpa-template/upload")
    async def upload_nfpa_template_copy(
        inspection_id: str,
        template_pdf: UploadFile = File(...),
    ) -> dict:
        with store.begin() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            filename = Path(template_pdf.filename or "nfpa-template.pdf").name
            if not filename.lower().endswith(".pdf"):
                return {"error": "Only PDF files are supported."}

            content = await template_pdf.read()
            if not content:
                return {"error": "Uploaded PDF was empty."}

            target_dir = ensure_inspection_upload_dir(inspection_id)
            stamped_name = f"nfpa-template-draft-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.pdf"
            target_path = target_dir / stamped_name
            target_path.write_bytes(content)

            session.add(
                SourceFile(
                    id=str(uuid4()),
                    inspection_id=inspection_id,
                    filename=stamped_name,
                    path=str(target_path),
                    kind="nfpa_template_draft",
                )
            )

            return {
                "inspection_id": inspection_id,
                "status": "saved",
                "saved_copy_filename": stamped_name,
                "original_filename": filename,
            }

    @router.get("/{inspection_id}/nfpa-template/open")
    def open_nfpa_template(inspection_id: str):
        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                raise HTTPException(status_code=404, detail="inspection not found")
            saved_path, saved_filename = latest_saved_nfpa_pdf_path(session, inspection_id)

        if saved_path:
            headers = {"Content-Disposition": f'inline; filename="{saved_filename}"'}
            return StreamingResponse(BytesIO(saved_path.read_bytes()), media_type="application/pdf", headers=headers)

        template_path = resolve_official_nfpa_template_path()
        if template_path is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Official NFPA template is not configured on this server. "
                    "Add NFPA72_template.pdf under docs/templates or set NFPA_TEMPLATE_PATH."
                ),
            )
        headers = {"Content-Disposition": f'inline; filename="{template_path.name}"'}
        return StreamingResponse(BytesIO(template_path.read_bytes()), media_type="application/pdf", headers=headers)

    @router.get("/{inspection_id}/nfpa-template/download")
    def download_nfpa_template(inspection_id: str):
        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                raise HTTPException(status_code=404, detail="inspection not found")
            saved_path, saved_filename = latest_saved_nfpa_pdf_path(session, inspection_id)

        if saved_path:
            headers = {"Content-Disposition": f'attachment; filename="{saved_filename}"'}
            return StreamingResponse(BytesIO(saved_path.read_bytes()), media_type="application/pdf", headers=headers)

        template_path = resolve_official_nfpa_template_path()
        if template_path is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No saved NFPA copy found, and official template is not configured on this server."
                ),
            )
        headers = {"Content-Disposition": f'attachment; filename="{template_path.name}"'}
        return StreamingResponse(BytesIO(template_path.read_bytes()), media_type="application/pdf", headers=headers)

    @router.get("/{inspection_id}/pdf-templates")
    def list_pdf_templates(inspection_id: str) -> dict:
        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            templates = []
            for item in list_templates():
                key = item["key"]
                path = resolve_template_path(key, env_lookup=dict(os.environ))
                has_template = bool(path)
                fields = []
                if path:
                    try:
                        fields = extract_template_fields(path)
                    except RuntimeError:
                        fields = []
                draft = (
                    session.query(InspectionPdfTemplateDraft)
                    .filter(
                        InspectionPdfTemplateDraft.inspection_id == inspection_id,
                        InspectionPdfTemplateDraft.template_key == key,
                    )
                    .first()
                )
                templates.append(
                    {
                        "key": key,
                        "label": item["label"],
                        "has_template": has_template,
                        "template_filename": path.name if path else "",
                        "field_count": len(fields),
                        "has_saved_draft": bool(draft),
                        "updated_at": draft.updated_at.isoformat() if draft and draft.updated_at else "",
                    }
                )
            return {"inspection_id": inspection_id, "templates": templates}

    @router.get("/{inspection_id}/pdf-templates/{template_key}")
    def get_pdf_template_draft(inspection_id: str, template_key: str) -> dict:
        meta = template_meta(template_key)
        if meta is None:
            raise HTTPException(status_code=404, detail="Unknown PDF template key.")

        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                raise HTTPException(status_code=404, detail="inspection not found")
            template_path = resolve_template_path(template_key, env_lookup=dict(os.environ))

        if template_path is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Template file for '{template_key}' is not configured on this server. "
                    f"Configure {meta['default_filename']} / {meta['env_var']}."
                ),
            )

        with store() as session:
            field_names = extract_template_fields(template_path)
            values = load_template_draft_values(session, inspection_id, template_key, field_names)
            draft_row = (
                session.query(InspectionPdfTemplateDraft)
                .filter(
                    InspectionPdfTemplateDraft.inspection_id == inspection_id,
                    InspectionPdfTemplateDraft.template_key == template_key,
                )
                .first()
            )

        return {
            "inspection_id": inspection_id,
            "template_key": template_key,
            "template_label": meta["label"],
            "template_filename": template_path.name,
            "field_names": field_names,
            "fields": values,
            "updated_at": draft_row.updated_at.isoformat() if draft_row and draft_row.updated_at else "",
        }

    @router.put("/{inspection_id}/pdf-templates/{template_key}")
    def save_pdf_template_draft(inspection_id: str, template_key: str, payload: dict = Body(default={})) -> dict:
        meta = template_meta(template_key)
        if meta is None:
            raise HTTPException(status_code=404, detail="Unknown PDF template key.")

        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                raise HTTPException(status_code=404, detail="inspection not found")
            template_path = resolve_template_path(template_key, env_lookup=dict(os.environ))

        if template_path is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Template file for '{template_key}' is not configured on this server. "
                    f"Configure {meta['default_filename']} / {meta['env_var']}."
                ),
            )

        field_names = extract_template_fields(template_path)
        fields = normalize_template_field_values(payload.get("fields"), field_names)

        with store.begin() as session:
            row = (
                session.query(InspectionPdfTemplateDraft)
                .filter(
                    InspectionPdfTemplateDraft.inspection_id == inspection_id,
                    InspectionPdfTemplateDraft.template_key == template_key,
                )
                .first()
            )
            now = datetime.now(timezone.utc)
            serialized = json.dumps(fields, ensure_ascii=True)
            if row is None:
                row = InspectionPdfTemplateDraft(
                    inspection_id=inspection_id,
                    template_key=template_key,
                    fields_json=serialized,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.fields_json = serialized
                row.updated_at = now

            return {
                "inspection_id": inspection_id,
                "template_key": template_key,
                "fields": fields,
                "updated_at": now.isoformat(),
                "status": "saved",
            }

    @router.get("/{inspection_id}/pdf-templates/{template_key}/preview")
    def preview_pdf_template_draft(inspection_id: str, template_key: str):
        meta = template_meta(template_key)
        if meta is None:
            raise HTTPException(status_code=404, detail="Unknown PDF template key.")

        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                raise HTTPException(status_code=404, detail="inspection not found")
            template_path = resolve_template_path(template_key, env_lookup=dict(os.environ))
            if template_path is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Template file for '{template_key}' is not configured on this server. "
                        f"Configure {meta['default_filename']} / {meta['env_var']}."
                    ),
                )
            field_names = extract_template_fields(template_path)
            values = load_template_draft_values(session, inspection_id, template_key, field_names)

        pdf_bytes = fill_template_pdf(template_path, values)
        headers = {"Content-Disposition": f'inline; filename="{template_path.name}"'}
        return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)

    @router.get("/{inspection_id}/pdf-templates/{template_key}/download")
    def download_pdf_template_draft(inspection_id: str, template_key: str):
        meta = template_meta(template_key)
        if meta is None:
            raise HTTPException(status_code=404, detail="Unknown PDF template key.")

        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                raise HTTPException(status_code=404, detail="inspection not found")
            template_path = resolve_template_path(template_key, env_lookup=dict(os.environ))
            if template_path is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Template file for '{template_key}' is not configured on this server. "
                        f"Configure {meta['default_filename']} / {meta['env_var']}."
                    ),
                )
            field_names = extract_template_fields(template_path)
            values = load_template_draft_values(session, inspection_id, template_key, field_names)

        pdf_bytes = fill_template_pdf(template_path, values)
        filename = default_template_download_name(template_key, inspection.store_number)
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)
