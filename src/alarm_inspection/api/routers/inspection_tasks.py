"""Administrator-managed tasks and auditable per-inspection checklist decisions."""
import json
from typing import Literal
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, StrictBool, StrictStr, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from alarm_inspection.api.auth_support import require_admin
from alarm_inspection.inspection_fields import native_fields, save_native_field, definition_lock
from alarm_inspection.domain.inspection_fields import validate_native_default
from alarm_inspection.domain.checklist import CHECKBOX_CHOICES, effective_answer, validate_default, validate_options, validate_answer
from alarm_inspection.domain.inspection_sections import InspectionSection
from alarm_inspection.storage import Inspection, InspectionTask, InspectionChecklistDecision


class TaskCreate(BaseModel):
    section: InspectionSection = "compliance"
    text: str = Field(min_length=1, max_length=200)
    position: int | None = Field(default=None, ge=1, le=10000, strict=True)
    input_type: Literal["checkbox", "textbox", "dropdown"] = "checkbox"
    options: list[StrictStr] = Field(default_factory=list, max_length=50)
    default_value: StrictStr = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_definition(self):
        self.options = validate_options(self.input_type, self.options)
        validate_default(self.input_type, self.default_value, self.options)
        return self

    @field_validator("text")
    @classmethod
    def clean_text(cls, value):
        value = " ".join(value.split())
        if not value:
            raise ValueError("Task description is required.")
        return value


class TaskUpdate(BaseModel):
    section: InspectionSection | None = None
    text: str | None = Field(default=None, min_length=1, max_length=200)
    position: int | None = Field(default=None, ge=1, le=10000, strict=True)
    active: StrictBool | None = None
    input_type: Literal["checkbox", "textbox", "dropdown"] | None = None
    options: list[StrictStr] | None = Field(default=None, max_length=50)
    default_value: StrictStr | None = Field(default=None, max_length=2000)

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
    completed: StrictBool | None = None
    value: StrictStr | None = Field(default=None, max_length=2000)


class TaskOrder(BaseModel):
    section: InspectionSection
    task_ids: list[StrictStr] = Field(max_length=10000)
    expected_order: list[StrictStr] = Field(max_length=10000)


class NativeFieldUpdate(BaseModel):
    model_config = {'extra': 'forbid'}
    text: StrictStr = Field(min_length=1, max_length=200)
    default_value: StrictStr = Field(max_length=500)


def serialize_task(task):
    return {"section": task.section, "id": task.id, "text": task.text, "position": task.position, "active": task.active, "input_type": task.input_type, "options": json.loads(task.options_json or "[]"), "default_value": task.default_value}


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
            return {"tasks": [serialize_task(task) for task in tasks], "builtin_fields": native_fields(session)}

    @router.patch('/builtin/{field_key}')
    def edit_native_field(field_key: str, payload: NativeFieldUpdate):
        with store.begin() as session:
            definition_lock(session)
            field = next((field for field in native_fields(session) if field['native_field'] == field_key), None)
            if field is None:
                raise HTTPException(status_code=404, detail='Store Data field not found.')
            label = ' '.join(payload.text.split())
            if not label:
                raise HTTPException(status_code=422, detail='A field label is required.')
            try:
                value = validate_native_default(field_key, payload.default_value)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            field.update(text=label, default_value=value)
            dates = {item['native_field']: item['default_value'] for item in native_fields(session)}
            dates[field_key] = value
            if dates['start_date'] and dates['completion_date'] and dates['completion_date'] < dates['start_date']:
                raise HTTPException(status_code=422, detail='End Date default must be on or after Start Date default.')
            save_native_field(session, field)
        return {'task': field}

    @router.post("", status_code=201)
    def add_task(payload: TaskCreate):
        try:
            with store.begin() as session:
                definition_lock(session)
                maximum = session.query(func.max(InspectionTask.position)).filter(InspectionTask.section == payload.section).scalar() or 0
                if payload.section == 'store_data':
                    maximum = max(maximum, *(field['position'] for field in native_fields(session)))
                position = payload.position or (maximum + 1)
                task = InspectionTask(id=str(uuid4()), text=payload.text, text_key=payload.text.casefold(),
                                      input_type=payload.input_type, options_json=json.dumps(payload.options),
                                      section=payload.section, default_value=payload.default_value, position=position, active=True, created_at=datetime.now(timezone.utc))
                session.add(task)
                session.flush()
                result = serialize_task(task)
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Task already exists. Edit or reactivate the existing task.") from exc
        return {"task": result}

    @router.put("/order")
    def reorder_tasks(payload: TaskOrder):
        with store.begin() as session:
            definition_lock(session)
            # Lock definitions so two reorders cannot partially interleave.
            tasks = session.query(InspectionTask).filter(InspectionTask.section == payload.section).order_by(
                InspectionTask.id).with_for_update().all()
            tasks.sort(key=lambda task: (task.position, task.created_at, task.id))
            fields = native_fields(session) if payload.section == 'store_data' else []
            ordered = sorted([*fields, *[serialize_task(task) for task in tasks]], key=lambda item: item['position'])
            current = [item['id'] for item in ordered]
            if len(set(payload.task_ids)) != len(payload.task_ids) or set(payload.task_ids) != set(current):
                raise HTTPException(status_code=409, detail="Section fields changed. Refresh before reordering.")
            if payload.expected_order != current:
                raise HTTPException(status_code=409, detail="Section order changed on another device. Refresh before reordering.")
            by_id = {task.id: task for task in tasks}
            builtins = {field['id']: field for field in fields}
            for position, task_id in enumerate(payload.task_ids, 1):
                if task_id in builtins:
                    builtins[task_id]['position'] = position
                    save_native_field(session, builtins[task_id])
                else:
                    by_id[task_id].position = position
        return {"status": "saved"}

    @router.patch("/{task_id}")
    def edit_task(task_id: str, payload: TaskUpdate):
        try:
            with store.begin() as session:
                definition_lock(session)
                task = session.get(InspectionTask, task_id)
                if task is None:
                    raise HTTPException(status_code=404, detail="Task not found.")
                input_type = payload.input_type or task.input_type
                options = payload.options if payload.options is not None else (json.loads(task.options_json or "[]") if input_type == "dropdown" else [])
                try:
                    options = validate_options(input_type, options)
                    # A changed type/choice list cannot retain an incompatible default.
                    default = payload.default_value if payload.default_value is not None else task.default_value
                    if payload.default_value is None and (input_type != task.input_type or input_type == "dropdown" and default not in ["", *options]):
                        default = ""
                    validate_default(input_type, default, options)
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
                if input_type != task.input_type or options != json.loads(task.options_json or "[]"):
                    task.options_json = json.dumps(options)
                task.input_type = input_type
                task.default_value = default
                if payload.text is not None:
                    task.text = payload.text
                    task.text_key = payload.text.casefold()
                if payload.section is not None:
                    task.section = payload.section
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
                same_type = bool(decision and decision.input_type == task.input_type)
                value = effective_answer(task, decision)
                completed = bool(value.strip())
                rows.append({**serialize_task(task), "completed": completed, "value": value,
                             "default_applied": decision is None and bool(value),
                             "previous_type": decision.input_type if decision and not same_type else None,
                             "removed_choice": bool(value and task.input_type == "dropdown" and value not in json.loads(task.options_json or "[]"))})
            return {"tasks": rows, "builtin_fields": native_fields(session), "completed_count": sum(row["completed"] for row in rows), "total_count": len(rows)}

    @router.patch("/{task_id}")
    def update_checklist(inspection_id: str, task_id: str, payload: ChecklistUpdate, request: Request):
        with store.begin() as session:
            check_inspection(session, inspection_id)
            task = session.get(InspectionTask, task_id)
            if task is None or not task.active:
                raise HTTPException(status_code=404, detail="Active task not found.")
            options = json.loads(task.options_json or "[]")
            try:
                completed, value = validate_answer(task.input_type, payload.completed, payload.value, options)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            session.add(InspectionChecklistDecision(
                id=str(uuid4()), inspection_id=inspection_id, task_id=task.id, task_text=task.text,
                input_type=task.input_type, value=value,
                options_json=json.dumps(CHECKBOX_CHOICES) if task.input_type == "checkbox" else task.options_json,
                completed=completed, decided_by=request.state.current_user.id,
                decided_at=datetime.now(timezone.utc),
            ))
        return {"task_id": task_id, "completed": completed, "value": value, "status": "saved"}

    return router
