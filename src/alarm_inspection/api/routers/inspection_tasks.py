"""Administrator-managed tasks and auditable per-inspection checklist decisions."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, StrictBool, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from alarm_inspection.api.auth_support import require_admin
from alarm_inspection.storage import Inspection, InspectionTask, InspectionChecklistDecision


class TaskCreate(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    position: int | None = Field(default=None, ge=1, le=10000, strict=True)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value):
        value = " ".join(value.split())
        if not value:
            raise ValueError("Task description is required.")
        return value


class TaskUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=200)
    position: int | None = Field(default=None, ge=1, le=10000, strict=True)
    active: StrictBool | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be empty.")
        if self.text is not None:
            self.text = " ".join(self.text.split())
            if not self.text:
                raise ValueError("Task description is required.")
        return self


class ChecklistUpdate(BaseModel):
    completed: StrictBool


def serialize_task(task):
    return {"id": task.id, "text": task.text, "position": task.position, "active": task.active}


def admin_only(request: Request):
    try:
        require_admin(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def create_admin_router(store):
    router = APIRouter(prefix="/api/admin/inspection-tasks", tags=["inspection-tasks"], dependencies=[Depends(admin_only)])

    @router.get("")
    def list_tasks():
        with store() as session:
            tasks = session.query(InspectionTask).order_by(InspectionTask.position, InspectionTask.created_at, InspectionTask.id).all()
            return {"tasks": [serialize_task(task) for task in tasks]}

    @router.post("", status_code=201)
    def add_task(payload: TaskCreate):
        try:
            with store.begin() as session:
                position = payload.position or ((session.query(func.max(InspectionTask.position)).scalar() or 0) + 1)
                task = InspectionTask(id=str(uuid4()), text=payload.text, text_key=payload.text.casefold(),
                                      position=position, active=True, created_at=datetime.now(timezone.utc))
                session.add(task)
                session.flush()
                result = serialize_task(task)
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Task already exists. Edit or reactivate the existing task.") from exc
        return {"task": result}

    @router.patch("/{task_id}")
    def edit_task(task_id: str, payload: TaskUpdate):
        try:
            with store.begin() as session:
                task = session.get(InspectionTask, task_id)
                if task is None:
                    raise HTTPException(status_code=404, detail="Task not found.")
                if payload.text is not None:
                    task.text = payload.text
                    task.text_key = payload.text.casefold()
                if payload.position is not None:
                    task.position = payload.position
                if payload.active is not None:
                    task.active = payload.active
                session.flush()
                result = serialize_task(task)
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Task already exists.") from exc
        return {"task": result}

    return router


def create_checklist_router(store):
    router = APIRouter(prefix="/api/inspections/{inspection_id}/checklist", tags=["inspection-checklist"])

    def check_inspection(session, inspection_id):
        row = session.get(Inspection, inspection_id)
        if row is None or row.status == "deleted":
            raise HTTPException(status_code=404, detail="Inspection not found.")

    @router.get("")
    def get_checklist(inspection_id: str):
        with store() as session:
            check_inspection(session, inspection_id)
            tasks = session.query(InspectionTask).filter(InspectionTask.active.is_(True)).order_by(
                InspectionTask.position, InspectionTask.created_at, InspectionTask.id).all()
            decisions = session.query(InspectionChecklistDecision).filter(
                InspectionChecklistDecision.inspection_id == inspection_id).order_by(
                InspectionChecklistDecision.decided_at.desc(), InspectionChecklistDecision.id.desc()).all()
            latest = {}
            for decision in decisions:
                latest.setdefault(decision.task_id, decision)
            rows = []
            for task in tasks:
                decision = latest.get(task.id)
                rows.append({**serialize_task(task), "completed": bool(decision and decision.completed)})
            return {"tasks": rows, "completed_count": sum(row["completed"] for row in rows), "total_count": len(rows)}

    @router.patch("/{task_id}")
    def update_checklist(inspection_id: str, task_id: str, payload: ChecklistUpdate, request: Request):
        with store.begin() as session:
            check_inspection(session, inspection_id)
            task = session.get(InspectionTask, task_id)
            if task is None or not task.active:
                raise HTTPException(status_code=404, detail="Active task not found.")
            session.add(InspectionChecklistDecision(
                id=str(uuid4()), inspection_id=inspection_id, task_id=task.id, task_text=task.text,
                completed=payload.completed, decided_by=request.state.current_user.id,
                decided_at=datetime.now(timezone.utc),
            ))
        return {"task_id": task_id, "completed": payload.completed, "status": "saved"}

    return router
