"""Persistent panel-type choices shared by administration and Points List intake."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from alarm_inspection.storage import PanelType, PointList

DEFAULT_PANEL_TYPES = ("Combo", "Fire", "Burglar", "Gas Station")


def clean_panel_type_name(value: str) -> str:
    name = " ".join(value.split())
    if not name or len(name) > 40:
        raise ValueError("Panel type name must be between 1 and 40 characters.")
    return name


def resolve_panel_type(session, value: str) -> str:
    name = clean_panel_type_name(value)
    row = session.query(PanelType).filter(PanelType.name_key == name.casefold()).first()
    if row is None:
        raise ValueError("Choose a configured panel type.")
    return row.name


def seed_panel_types(store) -> None:
    with store.begin() as session:
        legacy = [name for (name,) in session.query(PointList.category).distinct().all() if name and name.strip()]
        for value in (*DEFAULT_PANEL_TYPES, *legacy):
            name = clean_panel_type_name(value)
            if session.query(PanelType).filter(PanelType.name_key == name.casefold()).first():
                continue
            try:
                with session.begin_nested():
                    session.add(PanelType(id=str(uuid4()), name=name, name_key=name.casefold(),
                                          created_at=datetime.now(timezone.utc)))
                    session.flush()
            except IntegrityError:
                # Another application worker may have seeded this choice first.
                pass
