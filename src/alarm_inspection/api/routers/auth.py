from __future__ import annotations

from datetime import datetime, timezone
import secrets
from uuid import uuid4

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, Response

from alarm_inspection.api.auth_support import get_user_from_request, serialize_user
from alarm_inspection.api.security import SESSION_COOKIE, password_record, verify_password
from alarm_inspection.storage import User, UserSession


def create_router(store) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    @router.post("/login")
    def login(payload: dict = Body(default={})) -> Response:
        email = str(payload.get("email") or "").strip().lower()
        password = str(payload.get("password") or "")
        if not email or not password:
            return JSONResponse(status_code=400, content={"error": "Email and password are required."})

        with store.begin() as session:
            user = session.query(User).filter(User.email == email).first()
            if user is None or not user.is_active or not verify_password(password, user.password_hash):
                return JSONResponse(status_code=401, content={"error": "Invalid credentials."})

            token = secrets.token_urlsafe(36)
            now = datetime.now(timezone.utc)
            session.add(
                UserSession(
                    id=str(uuid4()),
                    user_id=user.id,
                    session_token=token,
                    created_at=now,
                    expires_at=now.replace(hour=23, minute=59, second=59, microsecond=0),
                )
            )
            response = JSONResponse(content={"user": serialize_user(user)})
            response.set_cookie(
                key=SESSION_COOKIE,
                value=token,
                httponly=True,
                samesite="lax",
                secure=False,
                max_age=60 * 60 * 24,
            )
            return response

    @router.get("/me")
    def auth_me(request: Request) -> dict:
        user = get_user_from_request(store, request, SESSION_COOKIE)
        if user is None:
            return {"authenticated": False}
        return {"authenticated": True, "user": serialize_user(user)}

    @router.post("/logout")
    def logout(request: Request) -> Response:
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            with store.begin() as session:
                session.query(UserSession).filter(UserSession.session_token == token).delete(synchronize_session=False)
        response = JSONResponse(content={"status": "logged_out"})
        response.delete_cookie(SESSION_COOKIE)
        return response

    @router.post("/reset-password")
    def reset_password(request: Request, payload: dict = Body(default={})) -> Response:
        user = get_user_from_request(store, request, SESSION_COOKIE)
        if user is None:
            return JSONResponse(status_code=401, content={"error": "Authentication required."})

        current_password = str(payload.get("current_password") or "")
        new_password = str(payload.get("new_password") or "")
        if not current_password or not new_password:
            return JSONResponse(status_code=400, content={"error": "Current and new passwords are required."})
        if len(new_password) < 8:
            return JSONResponse(status_code=400, content={"error": "New password must be at least 8 characters."})

        with store.begin() as session:
            db_user = session.get(User, user.id)
            if db_user is None or not verify_password(current_password, db_user.password_hash):
                return JSONResponse(status_code=400, content={"error": "Current password is incorrect."})
            db_user.password_hash = password_record(new_password)
            db_user.force_password_reset = False
            return JSONResponse(content={"status": "password_reset", "user": serialize_user(db_user)})

    return router
