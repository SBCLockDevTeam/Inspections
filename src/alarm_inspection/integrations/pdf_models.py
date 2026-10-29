"""Separate additive metadata; imported only when PDF integrations are enabled."""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from alarm_inspection.storage import Inspection, PointList


class PdfBase(DeclarativeBase):
    pass


class PdfSchemaState(PdfBase):
    __tablename__ = 'pdf_integration_schema'
    __table_args__ = (CheckConstraint('id = 1 AND version >= 1'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer)


class PdfIntegration(PdfBase):
    __tablename__ = 'pdf_integrations'
    __table_args__ = (CheckConstraint("key IN ('nfpa72','compliance')"), CheckConstraint('revision >= 1'))
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    active_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(
        'pdf_integration_versions.id', name='fk_pdf_active_version', use_alter=True), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class PdfIntegrationVersion(PdfBase):
    __tablename__ = 'pdf_integration_versions'
    __table_args__ = (CheckConstraint("status IN ('draft','published')"), CheckConstraint('revision >= 1'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    integration_key: Mapped[str] = mapped_column(ForeignKey('pdf_integrations.key'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='draft')
    revision: Mapped[int] = mapped_column(Integer, default=1)
    payload_json: Mapped[str] = mapped_column(Text)
    payload_sha256: Mapped[str] = mapped_column(String(64))
    verification_json: Mapped[str] = mapped_column(Text, default='{}')
    created_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InspectionFormDecision(PdfBase):
    __tablename__ = 'inspection_form_decisions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(ForeignKey(Inspection.id), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey('pdf_integration_versions.id'), index=True)
    point_list_id: Mapped[str | None] = mapped_column(ForeignKey(PointList.id), nullable=True)
    input_id: Mapped[str] = mapped_column(String(80), index=True)
    input_schema_sha256: Mapped[str] = mapped_column(String(64))
    answer_json: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[str] = mapped_column(String(36))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PdfExportArtifact(PdfBase):
    __tablename__ = 'pdf_export_artifacts'
    __table_args__ = (
        CheckConstraint("purpose IN ('test','preview','final')"),
        CheckConstraint("status IN ('pending','ready','failed')"),
        CheckConstraint("status <> 'ready' OR (sha256 IS NOT NULL AND size IS NOT NULL AND size >= 0)"),
        CheckConstraint("purpose <> 'final' OR preview_id IS NOT NULL"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspection_id: Mapped[str] = mapped_column(ForeignKey(Inspection.id), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey('pdf_integration_versions.id'), index=True)
    config_sha256: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    snapshot_json: Mapped[str] = mapped_column(Text)
    file_key: Mapped[str] = mapped_column(String(250), unique=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    renderer_version: Mapped[str] = mapped_column(String(80))
    download_filename: Mapped[str] = mapped_column(String(255))
    confirmation_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preview_id: Mapped[str | None] = mapped_column(ForeignKey('pdf_export_artifacts.id'), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PdfIntegrationAuditEntry(PdfBase):
    __tablename__ = 'pdf_integration_audit_entries'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    integration_key: Mapped[str] = mapped_column(ForeignKey('pdf_integrations.key'), index=True)
    version_id: Mapped[str | None] = mapped_column(ForeignKey('pdf_integration_versions.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    details_json: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[str] = mapped_column(String(36))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
