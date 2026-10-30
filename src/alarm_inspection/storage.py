"""Small persistence boundary for inspection intake."""

from __future__ import annotations

import os
import logging
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import Boolean, Date, DateTime, String, Text, create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from alarm_inspection.domain.inspection_names import build_inspection_name, location_from_address


class Base(DeclarativeBase):
    pass


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    store_number: Mapped[str] = mapped_column(String(100))
    store_type: Mapped[str] = mapped_column(String(80), default="Walmart - Supercenter")
    address: Mapped[str] = mapped_column(String(500))
    city: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(2), default="")
    inspector_name: Mapped[str] = mapped_column(String(120), default="")
    start_date: Mapped[date] = mapped_column(Date)
    completion_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    @property
    def name(self) -> str:
        return build_inspection_name(self.store_number, self.city or "", self.state or "", self.start_date)


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
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class InspectionAuditEntry(Base):
    __tablename__ = "inspection_audit_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(String(36), index=True)
    point_list_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(80))
    details_json: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[str] = mapped_column(String(36))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PanelType(Base):
    __tablename__ = "panel_types"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    name_key: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InspectionTask(Base):
    __tablename__ = "inspection_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    text: Mapped[str] = mapped_column(String(200))
    text_key: Mapped[str] = mapped_column(String(600), unique=True)
    input_type: Mapped[str] = mapped_column(String(20), default="checkbox")
    options_json: Mapped[str] = mapped_column(Text, default="[]")
    section: Mapped[str] = mapped_column(String(20), default="compliance", server_default="compliance", nullable=False)
    position: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InspectionChecklistDecision(Base):
    __tablename__ = "inspection_checklist_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(String(36), index=True)
    task_id: Mapped[str] = mapped_column(String(36), index=True)
    task_text: Mapped[str] = mapped_column(String(200))
    input_type: Mapped[str] = mapped_column(String(20), default="checkbox")
    value: Mapped[str] = mapped_column(String(2000), default="")
    options_json: Mapped[str] = mapped_column(Text, default="[]")
    completed: Mapped[bool] = mapped_column(Boolean)
    decided_by: Mapped[str] = mapped_column(String(36))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
    location: Mapped[str] = mapped_column(String(500), default="")
    device_highlighted: Mapped[bool] = mapped_column(Boolean, default=False)
    device_event_missing: Mapped[bool] = mapped_column(Boolean, default=False)
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


class PointListPendingEventDate(Base):
    __tablename__ = "point_list_pending_event_dates"

    inspection_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    point_list_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    point_address: Mapped[int] = mapped_column(primary_key=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_filename: Mapped[str] = mapped_column(String(255), default="")


class InspectionPdfDraft(Base):
    __tablename__ = "inspection_pdf_drafts"

    inspection_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fields_json: Mapped[str] = mapped_column(String(20000), default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InspectionPdfTemplateDraft(Base):
    __tablename__ = "inspection_pdf_template_drafts"

    inspection_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    template_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    fields_json: Mapped[str] = mapped_column(String(50000), default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def open_store():
    url = os.getenv("DATABASE_URL")
    if not url:
        default_db = Path(tempfile.gettempdir()) / "alarm-inspection.db"
        default_db.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{default_db.as_posix()}"

    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            engine = create_engine(url, pool_pre_ping=True)
            Base.metadata.create_all(engine)
            _ensure_inspection_columns(engine)
            _ensure_point_list_decision_columns(engine)
            _ensure_checklist_columns(engine)
            _ensure_point_list_columns(engine)
            # Optional integration metadata is isolated from existing tables and
            # imports. A failure here must not disable current inspection work.
            from alarm_inspection.integrations.pdf_feature import enabled
            pdf_available = False
            if enabled():
                try:
                    from alarm_inspection.integrations.pdf_schema import initialize_pdf_store
                    initialize_pdf_store(engine)
                    pdf_available = True
                except Exception:
                    logging.getLogger(__name__).error('PDF integrations unavailable; existing inspection workflows remain enabled.')
            return sessionmaker(bind=engine, expire_on_commit=False,
                                info={'pdf_integrations_available': pdf_available})
        except SQLAlchemyError as exc:  # pragma: no cover - depends on external DB readiness
            last_error = exc
            if attempt == 5 or url.startswith("sqlite"):
                raise
            time.sleep(2)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Unable to initialize the inspection database store.")


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
    for column, length in (("city", 120), ("state", 2)):
        if column not in existing_columns:
            statements.append(f"ALTER TABLE inspections ADD COLUMN {column} VARCHAR({length}) DEFAULT ''")
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        rows = connection.execute(text(
            "SELECT id, address, city, state FROM inspections WHERE city = '' OR state = '' OR city IS NULL OR state IS NULL"
        )).mappings().all()
        for row in rows:
            city, state = location_from_address(row["address"] or "")
            connection.execute(text("UPDATE inspections SET city = :city, state = :state WHERE id = :id"),
                               {"id": row["id"], "city": row["city"] or city, "state": row["state"] or state})


def _ensure_point_list_decision_columns(engine) -> None:
    existing_columns = {
        column["name"]
        for column in inspect(engine).get_columns("point_list_decisions")
    }
    statements: list[str] = []
    if "location" not in existing_columns:
        statements.append(
            "ALTER TABLE point_list_decisions ADD COLUMN location VARCHAR(500) DEFAULT ''"
        )
    if "device_highlighted" not in existing_columns:
        statements.append(
            "ALTER TABLE point_list_decisions ADD COLUMN device_highlighted BOOLEAN DEFAULT FALSE"
        )
    if "device_event_missing" not in existing_columns:
        statements.append(
            "ALTER TABLE point_list_decisions ADD COLUMN device_event_missing BOOLEAN DEFAULT FALSE"
        )
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _ensure_checklist_columns(engine) -> None:
    additions = {
        "inspection_tasks": {"section": "VARCHAR(20) NOT NULL DEFAULT 'compliance'", "input_type": "VARCHAR(20) DEFAULT 'checkbox'", "options_json": "TEXT DEFAULT '[]'"},
        "inspection_checklist_decisions": {"input_type": "VARCHAR(20) DEFAULT 'checkbox'", "value": "VARCHAR(2000) DEFAULT ''", "options_json": "TEXT DEFAULT '[]'"},
    }
    for table, columns in additions.items():
        existing = {column["name"] for column in inspect(engine).get_columns(table)}
        with engine.begin() as connection:
            if engine.dialect.name == 'sqlite' and table == 'inspection_tasks' and 'section' not in existing:
                # SQLite needs an explicit BEGIN to make column creation and
                # the one-time field move atomic together.
                connection.exec_driver_sql('BEGIN IMMEDIATE')
            for name, definition in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
                    if table == "inspection_tasks" and name == "section":
                        # One-time move only. IDs, answers, types and options stay intact.
                        connection.execute(text("UPDATE inspection_tasks SET section = 'nfpa72' "
                            "WHERE lower(trim(text)) IN ('panel model', 'firmware version')"))


def _ensure_point_list_columns(engine) -> None:
    existing = {column["name"] for column in inspect(engine).get_columns("point_lists")}
    with engine.begin() as connection:
        for name, definition in (("deleted_at", "TIMESTAMP WITH TIME ZONE" if engine.dialect.name == "postgresql" else "DATETIME"),
                                 ("deleted_by", "VARCHAR(36)")):
            if name not in existing:
                connection.execute(text(f"ALTER TABLE point_lists ADD COLUMN {name} {definition}"))
