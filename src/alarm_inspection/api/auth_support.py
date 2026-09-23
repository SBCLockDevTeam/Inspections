from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from fastapi import Request

from alarm_inspection.api.security import DEFAULT_PASSWORD_FALLBACK, DEFAULT_PASSWORD_SETTING_KEY, password_record
from alarm_inspection.storage import AppSetting, User, UserSession


def serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "is_admin": bool(user.is_admin),
        "force_password_reset": bool(user.force_password_reset),
    }


def get_default_password(session) -> str:
    setting = session.get(AppSetting, DEFAULT_PASSWORD_SETTING_KEY)
    if setting is None or not setting.value:
        return DEFAULT_PASSWORD_FALLBACK
    return setting.value


def set_default_password(session, value: str) -> str:
    clean_value = value.strip() or DEFAULT_PASSWORD_FALLBACK
    setting = session.get(AppSetting, DEFAULT_PASSWORD_SETTING_KEY)
    now = datetime.now(timezone.utc)
    if setting is None:
        setting = AppSetting(
            key=DEFAULT_PASSWORD_SETTING_KEY,
            value=clean_value,
            updated_at=now,
        )
        session.add(setting)
    else:
        setting.value = clean_value
        setting.updated_at = now
    return clean_value


def get_force_password_reset_default(session) -> bool:
    from alarm_inspection.api.security import (
        FORCE_PASSWORD_RESET_DEFAULT_FALLBACK,
        FORCE_PASSWORD_RESET_DEFAULT_SETTING_KEY,
    )

    setting = session.get(AppSetting, FORCE_PASSWORD_RESET_DEFAULT_SETTING_KEY)
    if setting is None or setting.value is None:
        return FORCE_PASSWORD_RESET_DEFAULT_FALLBACK
    return str(setting.value).strip().lower() in {"1", "true", "yes", "on"}


def set_force_password_reset_default(session, value: bool) -> bool:
    from alarm_inspection.api.security import FORCE_PASSWORD_RESET_DEFAULT_SETTING_KEY

    clean_value = bool(value)
    stored_value = "1" if clean_value else "0"
    setting = session.get(AppSetting, FORCE_PASSWORD_RESET_DEFAULT_SETTING_KEY)
    now = datetime.now(timezone.utc)
    if setting is None:
        setting = AppSetting(
            key=FORCE_PASSWORD_RESET_DEFAULT_SETTING_KEY,
            value=stored_value,
            updated_at=now,
        )
        session.add(setting)
    else:
        setting.value = stored_value
        setting.updated_at = now
    return clean_value


def seed_initial_admin(store) -> None:
    admin_email = "john.porter@securitybuildingcontrols.com"
    with store.begin() as session:
        default_password = get_default_password(session)
        set_default_password(session, default_password)
        set_force_password_reset_default(session, get_force_password_reset_default(session))
        existing = session.query(User).filter(User.email == admin_email).first()
        if existing is not None:
            return
        session.add(
            User(
                id=str(uuid4()),
                email=admin_email,
                password_hash=password_record(default_password),
                is_admin=True,
                force_password_reset=True,
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
        )


def get_user_from_request(store, request: "Request", session_cookie: str) -> User | None:
    token = request.cookies.get(session_cookie)
    if not token:
        return None
    now = datetime.now(timezone.utc)
    with store() as session:
        session_row = (
            session.query(UserSession)
            .filter(UserSession.session_token == token, UserSession.expires_at >= now)
            .first()
        )
        if session_row is None:
            return None
        user = session.get(User, session_row.user_id)
        if user is None or not user.is_active:
            return None
        return user


def require_admin(request: "Request") -> User:
    user = getattr(request.state, "current_user", None)
    if user is None or not bool(user.is_admin):
        raise PermissionError("Admin privileges are required.")
    return user
