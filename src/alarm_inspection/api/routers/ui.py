from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response


def create_router() -> APIRouter:
    router = APIRouter(tags=["ui"])

    @router.get("/", response_class=HTMLResponse)
    def home() -> str:
        html_path = Path(__file__).resolve().parents[1] / "index.html"
        return html_path.read_text(encoding="utf-8")

    @router.get("/review.js")
    def review_script() -> Response:
        script_path = Path(__file__).resolve().parents[1] / "review.js"
        script = script_path.read_text(encoding="utf-8")
        return Response(content=script, media_type="application/javascript")

    return router
