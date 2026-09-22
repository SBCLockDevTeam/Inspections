"""Small persistence boundary for inspection intake."""

from __future__ import annotations

import os
import tempfile
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import Boolean, Date, DateTime, String, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    store_number: Mapped[str] = mapped_column(String(100))
    store_type: Mapped[str] = mapped_column(String(80), default="Walmart - Supercenter")
    address: Mapped[str] = mapped_column(String(500))
    inspector_name: Mapped[str] = mapped_column(String(120), default="")
    start_date: Mapped[date] = mapped_column(Date)
    completion_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(600))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    force_password_reset: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    session_token: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(String(1000), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PointList(Base):
    __tablename__ = "point_lists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(String(36), index=True)
    category: Mapped[str] = mapped_column(String(40))
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(1000))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceFile(Base):
    __tablename__ = "source_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(String(36), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(1000))
    kind: Mapped[str] = mapped_column(String(40))


class PointListDecision(Base):
    __tablename__ = "point_list_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(String(36), index=True)
    point_list_id: Mapped[str] = mapped_column(String(36), index=True)
    address: Mapped[int | None] = mapped_column(nullable=True)
    text: Mapped[str] = mapped_column(String(500))
    accepted: Mapped[bool] = mapped_column(default=True)
    deleted: Mapped[bool] = mapped_column(default=False)
    reason: Mapped[str] = mapped_column(String(200), default="technician review")


class PointListEventDate(Base):
    __tablename__ = "point_list_event_dates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(String(36), index=True)
    point_list_id: Mapped[str] = mapped_column(String(36), index=True)
    point_address: Mapped[int] = mapped_column(index=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_filename: Mapped[str] = mapped_column(String(255), default="")


def open_store():
    url = os.getenv("DATABASE_URL")
    if not url:
        default_db = Path(tempfile.gettempdir()) / "alarm-inspection.db"
        default_db.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{default_db.as_posix()}"
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    _ensure_inspection_columns(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _ensure_inspection_columns(engine) -> None:
    existing_columns = {
        column["name"]
        for column in inspect(engine).get_columns("inspections")
    }
    statements: list[str] = []
    if "store_type" not in existing_columns:
        statements.append(
            "ALTER TABLE inspections ADD COLUMN store_type VARCHAR(80) DEFAULT 'Walmart - Supercenter'"
        )
    if "inspector_name" not in existing_columns:
        statements.append(
            "ALTER TABLE inspections ADD COLUMN inspector_name VARCHAR(120) DEFAULT ''"
        )
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
