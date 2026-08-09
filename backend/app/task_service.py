"""Shared Task-store logic. Both POST /tasks and the /ingest pipeline (Stage 6)
go through here, so validation, dedup, and revision history are identical."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import normalize_candidate_id
from .models import Task, TaskRevision
from .schemas import TaskCreateIn, TaskPatchIn

# Fields that participate in the revision diff / are patchable per §5.3.
MUTABLE_FIELDS = (
    "title",
    "description",
    "assignee_id",
    "category",
    "priority",
    "due_date",
    "deal_value_inr",
    "company_name",
    "confidence",
)


def _coerce(field: str, value: Any) -> Any:
    """Enum objects -> their .value; leave everything else alone."""
    return getattr(value, "value", value)


def get_task(db: Session, task_id: str) -> Task | None:
    return db.get(Task, task_id)


def find_by_source(db: Session, candidate_id: str, source_email_id: str) -> Task | None:
    cid = normalize_candidate_id(candidate_id)
    return db.scalar(
        select(Task).where(
            Task.candidate_id == cid, Task.source_email_id == source_email_id
        )
    )


def find_by_thread(db: Session, candidate_id: str, thread_id: str) -> Task | None:
    cid = normalize_candidate_id(candidate_id)
    return db.scalar(
        select(Task)
        .where(Task.candidate_id == cid, Task.thread_id == thread_id)
        .order_by(Task.created_at.asc())
    )


def create_task(db: Session, data: TaskCreateIn) -> tuple[Task, bool]:
    """Create a task. Dedup on (candidate_id, source_email_id): if one exists,
    return it untouched with created=False (replay / idempotency)."""
    cid = normalize_candidate_id(data.candidate_id)
    existing = find_by_source(db, cid, data.source_email_id)
    if existing is not None:
        return existing, False

    task = Task(
        candidate_id=cid,
        source_email_id=data.source_email_id,
        thread_id=data.thread_id,
        title=data.title,
        description=data.description,
        assignee_id=_coerce("assignee_id", data.assignee_id),
        category=_coerce("category", data.category),
        priority=_coerce("priority", data.priority),
        due_date=data.due_date,
        deal_value_inr=data.deal_value_inr,
        company_name=data.company_name,
        confidence=data.confidence,
    )
    db.add(task)
    db.flush()
    return task, True


def _next_revision_index(db: Session, task_id: str) -> int:
    from sqlalchemy import func

    n = db.scalar(select(func.count(TaskRevision.id)).where(TaskRevision.task_id == task_id))
    return int(n or 0) + 1


def _diff_and_apply(task: Task, changes: dict[str, Any]) -> dict[str, dict]:
    """Apply changes to the task, returning {field: {from, to}} for fields that
    actually changed. Dates are serialised to ISO for the JSON diff."""
    diff: dict[str, dict] = {}
    for field, new_value in changes.items():
        if field not in MUTABLE_FIELDS:
            continue
        new_value = _coerce(field, new_value)
        old_value = getattr(task, field)
        if old_value == new_value:
            continue
        setattr(task, field, new_value)
        diff[field] = {
            "from": old_value.isoformat() if isinstance(old_value, date) else old_value,
            "to": new_value.isoformat() if isinstance(new_value, date) else new_value,
        }
    return diff


def apply_update(
    db: Session,
    task: Task,
    changes: dict[str, Any],
    *,
    source_email_id: str | None = None,
) -> tuple[Task, dict[str, dict]]:
    """Apply a subset of mutable fields, write a revision row with the diff if
    anything changed, and return (task, diff)."""
    diff = _diff_and_apply(task, changes)
    if diff:
        rev = TaskRevision(
            task_id=task.task_id,
            candidate_id=task.candidate_id,
            thread_id=task.thread_id,
            source_email_id=source_email_id or task.source_email_id,
            changed_fields=diff,
            revision_index=_next_revision_index(db, task.task_id),
        )
        db.add(rev)
        db.flush()
    return task, diff


def patch_task(
    db: Session, task_id: str, patch: TaskPatchIn, *, source_email_id: str | None = None
) -> tuple[Task | None, dict[str, dict]]:
    task = get_task(db, task_id)
    if task is None:
        return None, {}
    changes = patch.model_dump(exclude_unset=True)
    return apply_update(db, task, changes, source_email_id=source_email_id)


def list_tasks(
    db: Session,
    candidate_id: str,
    *,
    thread_id: str | None = None,
    source_email_id: str | None = None,
    assignee_id: str | None = None,
) -> list[Task]:
    cid = normalize_candidate_id(candidate_id)
    stmt = select(Task).where(Task.candidate_id == cid)
    if thread_id:
        stmt = stmt.where(Task.thread_id == thread_id)
    if source_email_id:
        stmt = stmt.where(Task.source_email_id == source_email_id)
    if assignee_id:
        stmt = stmt.where(Task.assignee_id == assignee_id)
    stmt = stmt.order_by(Task.created_at.asc())
    return list(db.scalars(stmt).all())


def delete_task(db: Session, task_id: str) -> bool:
    task = db.get(Task, task_id)
    if task is None:
        return False
    db.delete(task)
    db.flush()
    return True
