"""Small persistence boundary for inspection intake."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import Date, DateTime, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    store_number: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(500))
    start_date: Mapped[date] = mapped_column(Date)
    completion_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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


def open_store():
    url = os.getenv("DATABASE_URL", "sqlite:////tmp/alarm-inspection.db")
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
