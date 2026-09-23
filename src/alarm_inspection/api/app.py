"""HTTP API boundary and application bootstrap."""

from __future__ import annotations

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
except ImportError:  # Allows domain tests to run without web dependencies.
    FastAPI = None

from alarm_inspection.api.common import UPLOAD_ROOT

# Compatibility aliases used by existing tests.
_UPLOAD_ROOT = UPLOAD_ROOT


def _ensure_inspection_upload_dir(inspection_id: str):
    upload_dir = _UPLOAD_ROOT / inspection_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def create_app():
    if FastAPI is None:
        raise RuntimeError("Install the 'web' optional dependencies to run the API")

    from alarm_inspection.api.auth_support import get_user_from_request, seed_initial_admin
    from alarm_inspection.api.routers.admin import create_router as create_admin_router
    from alarm_inspection.api.routers.auth import create_router as create_auth_router
    from alarm_inspection.api.routers.inspections import create_router as create_inspections_router
    from alarm_inspection.api.routers.point_lists import create_router as create_point_lists_router
    from alarm_inspection.api.routers.ui import create_router as create_ui_router
    from alarm_inspection.api.security import SESSION_COOKIE
    from alarm_inspection.storage import open_store

    app = FastAPI(title="Alarm Inspection Processor", version="0.1.0")
    store = open_store()

    seed_initial_admin(store)

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        if path in {
            "/api/auth/login",
            "/api/auth/logout",
            "/api/auth/me",
            "/api/auth/reset-password",
        }:
            return await call_next(request)

        user = get_user_from_request(store, request, SESSION_COOKIE)
        if user is None:
            return JSONResponse(status_code=401, content={"error": "Authentication required."})
        if user.force_password_reset and not user.is_admin:
            return JSONResponse(
                status_code=403,
                content={"error": "Password reset is required before continuing."},
            )
        request.state.current_user = user
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(create_ui_router())
    app.include_router(create_auth_router(store))
    app.include_router(create_admin_router(store))
    app.include_router(create_inspections_router(store))
    app.include_router(create_point_lists_router())
    return app


app = create_app() if FastAPI is not None else None
