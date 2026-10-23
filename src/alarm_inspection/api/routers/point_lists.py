from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, UploadFile

from alarm_inspection.api.common import UPLOAD_ROOT
from alarm_inspection.intake.points_list import parse_xlsx
from alarm_inspection.api.panel_types import resolve_panel_type
from alarm_inspection.storage import PanelType


def create_router(store) -> APIRouter:
    router = APIRouter(prefix="/api/point-lists", tags=["point-lists"])

    @router.get("/types", tags=["panel-types"])
    def list_panel_types() -> dict:
        with store() as session:
            rows = session.query(PanelType).order_by(PanelType.name.asc()).all()
            return {"panel_types": [{"id": row.id, "name": row.name} for row in rows]}

    @router.post("/preview")
    async def preview_points_list(
        points_files: list[UploadFile] = File(...),
        point_list_categories: list[str] = Form(default=[]),
    ) -> dict:
        if point_list_categories and len(point_list_categories) != len(points_files):
            return {"error": "Each Points List must have a matching security-panel category."}

        if point_list_categories:
            try:
                with store() as session:
                    point_list_categories = [resolve_panel_type(session, name) for name in point_list_categories]
            except ValueError as exc:
                return {"error": str(exc)}
        previews = []
        for index, points_file in enumerate(points_files):
            filename = Path(points_file.filename or f"points-{index + 1}.xlsx").name
            if not filename.lower().endswith(".xlsx"):
                return {"error": "The first parser supports XLSX files; PDF and legacy XLS need a separate adapter."}
            preview_path = UPLOAD_ROOT / f"preview-{uuid4()}-{filename}"
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.write_bytes(await points_file.read())
            try:
                rows = parse_xlsx(preview_path)
            except ValueError as exc:
                return {"error": f"{filename}: {exc}"}
            previews.append(
                {
                    "filename": filename,
                    "category": point_list_categories[index] if point_list_categories else "",
                    "accepted": sum(row["accepted"] for row in rows),
                    "rejected": sum(not row["accepted"] for row in rows),
                    "rows": rows,
                }
            )

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

    return router
