"""Append-only records of explicit technician changes."""
from datetime import datetime, timezone
import json
from uuid import uuid4

from alarm_inspection.storage import InspectionAuditEntry


def record_decision(session, request, inspection_id, point_list_id, action, details):
    session.add(InspectionAuditEntry(
        id=str(uuid4()), inspection_id=inspection_id, point_list_id=point_list_id,
        action=action, details_json=json.dumps(details, default=str),
        decided_by=request.state.current_user.id, decided_at=datetime.now(timezone.utc),
    ))
