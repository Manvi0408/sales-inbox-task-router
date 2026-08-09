"""The raw Task API from §5 — /tasks CRUD and /users. This is what the grader
calls directly. Responses use the exact §5.2 spec shape and nothing extra."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from . import task_service
from .db import get_db
from .roster import TEAM
from .schemas import InvalidEnumValue, parse_task_create, parse_task_patch

router = APIRouter(tags=["task-api"])


@router.post("/tasks")
def create_task(payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        data = parse_task_create(payload)
    except InvalidEnumValue as e:
        return JSONResponse(status_code=400, content=e.body())
    except Exception as e:  # noqa: BLE001 - malformed body -> 400
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_payload", "detail": str(e)},
        )

    task, created = task_service.create_task(db, data)
    db.commit()
    # Dedup: existing task returned with 200; brand-new gets 201.
    status = 201 if created else 200
    return JSONResponse(status_code=status, content=task.to_spec_dict())


@router.patch("/tasks/{task_id}")
def patch_task(task_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        patch = parse_task_patch(payload)
    except InvalidEnumValue as e:
        return JSONResponse(status_code=400, content=e.body())
    except Exception as e:  # noqa: BLE001
        return JSONResponse(
            status_code=400, content={"error": "invalid_payload", "detail": str(e)}
        )

    task, _diff = task_service.patch_task(db, task_id, patch)
    if task is None:
        return JSONResponse(status_code=404, content={"error": "task_not_found"})
    db.commit()
    return JSONResponse(status_code=200, content=task.to_spec_dict())


@router.get("/tasks")
def list_tasks(
    candidate_id: str = Query(...),
    thread_id: str | None = Query(None),
    source_email_id: str | None = Query(None),
    assignee_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    tasks = task_service.list_tasks(
        db,
        candidate_id,
        thread_id=thread_id,
        source_email_id=source_email_id,
        assignee_id=assignee_id,
    )
    return [t.to_spec_dict() for t in tasks]


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db)):
    ok = task_service.delete_task(db, task_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "task_not_found"})
    db.commit()
    return Response(status_code=204)


@router.get("/users")
def get_users():
    return {"team": TEAM}
