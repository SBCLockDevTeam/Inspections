from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, Response

from alarm_inspection.api.auth_support import get_default_password, require_admin, serialize_user, set_default_password
from alarm_inspection.api.common import as_bool
from alarm_inspection.api.security import password_record
from alarm_inspection.storage import User, UserSession


def create_router(store) -> APIRouter:
    router = APIRouter(prefix="/api/admin", tags=["admin"])

    @router.get("/users")
    def admin_list_users(request: Request) -> Response:
        try:
            require_admin(request)
        except PermissionError as exc:
            return JSONResponse(status_code=403, content={"error": str(exc)})
        with store() as session:
            users = session.query(User).order_by(User.email.asc()).all()
            return JSONResponse(
                content={
                    "users": [
                        {
                            "id": user.id,
                            "email": user.email,
                            "is_admin": bool(user.is_admin),
                            "force_password_reset": bool(user.force_password_reset),
                            "is_active": bool(user.is_active),
                        }
                        for user in users
                    ]
                }
            )

    @router.get("/settings")
    def admin_get_settings(request: Request) -> Response:
        try:
            require_admin(request)
        except PermissionError as exc:
            return JSONResponse(status_code=403, content={"error": str(exc)})
        with store.begin() as session:
            default_password = get_default_password(session)
            set_default_password(session, default_password)
            return JSONResponse(content={"default_password": default_password})

    @router.patch("/settings")
    def admin_update_settings(request: Request, payload: dict = Body(default={})) -> Response:
        try:
            require_admin(request)
        except PermissionError as exc:
            return JSONResponse(status_code=403, content={"error": str(exc)})
        candidate = str(payload.get("default_password") or "").strip()
        if len(candidate) < 4:
            return JSONResponse(status_code=400, content={"error": "Default password must be at least 4 characters."})
        with store.begin() as session:
            updated = set_default_password(session, candidate)
            return JSONResponse(content={"status": "updated", "default_password": updated})

    @router.post("/users")
    def admin_add_user(request: Request, payload: dict = Body(default={})) -> Response:
        try:
            require_admin(request)
        except PermissionError as exc:
            return JSONResponse(status_code=403, content={"error": str(exc)})

        email = str(payload.get("email") or "").strip().lower()
        is_admin = as_bool(payload.get("is_admin"), default=False)
        if not email:
            return JSONResponse(status_code=400, content={"error": "Email is required."})

        with store.begin() as session:
            existing = session.query(User).filter(User.email == email).first()
            if existing is not None:
                return JSONResponse(status_code=400, content={"error": "User already exists."})
            default_password = get_default_password(session)
            new_user = User(
                id=str(uuid4()),
                email=email,
                password_hash=password_record(default_password),
                is_admin=is_admin,
                force_password_reset=True,
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            session.add(new_user)
            return JSONResponse(content={"status": "created", "user": serialize_user(new_user)})

    @router.patch("/users/{user_id}")
    def admin_update_user(user_id: str, request: Request, payload: dict = Body(default={})) -> Response:
        try:
            admin_user = require_admin(request)
        except PermissionError as exc:
            return JSONResponse(status_code=403, content={"error": str(exc)})

        with store.begin() as session:
            target = session.get(User, user_id)
            if target is None:
                return JSONResponse(status_code=404, content={"error": "User not found."})
            if "is_admin" in payload:
                target.is_admin = as_bool(payload.get("is_admin"), default=bool(target.is_admin))
            if "force_password_reset" in payload:
                target.force_password_reset = as_bool(
                    payload.get("force_password_reset"),
                    default=bool(target.force_password_reset),
                )
            if as_bool(payload.get("reset_password"), default=False):
                default_password = get_default_password(session)
                target.password_hash = password_record(default_password)
                target.force_password_reset = True
            if user_id == admin_user.id and not target.is_admin:
                return JSONResponse(status_code=400, content={"error": "You cannot remove your own admin access."})
            return JSONResponse(content={"status": "updated", "user": serialize_user(target)})

    @router.delete("/users/{user_id}")
    def admin_delete_user(user_id: str, request: Request) -> Response:
        try:
            admin_user = require_admin(request)
        except PermissionError as exc:
            return JSONResponse(status_code=403, content={"error": str(exc)})
        if user_id == admin_user.id:
            return JSONResponse(status_code=400, content={"error": "You cannot delete your own account."})

        with store.begin() as session:
            target = session.get(User, user_id)
            if target is None:
                return JSONResponse(status_code=404, content={"error": "User not found."})
            session.query(UserSession).filter(UserSession.user_id == user_id).delete(synchronize_session=False)
            session.delete(target)
            return JSONResponse(content={"status": "deleted", "user_id": user_id})

    return router
