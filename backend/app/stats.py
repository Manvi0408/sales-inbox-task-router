"""/api/stats and /api/tasks — the backend's own wrappers for the frontend.
These read stored ground truth and may add fields the grader doesn't care about
(skip reasons, reasoning, rules fired, revision counts)."""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import normalize_candidate_id, settings
from .db import get_db
from .models import EmailRecord, Task, TaskRevision

router = APIRouter(prefix="/api", tags=["app"])


@router.post("/reset")
def api_reset(payload: dict = Body(default=None), candidate_id: str = Query(default=None),
              db: Session = Depends(get_db)):
    """Wipe all tasks and logs for this candidate. Destructive — the frontend
    guards it behind a confirmation dialog."""
    raw = (payload or {}).get("candidate_id") or candidate_id or settings.CANDIDATE_ID
    cid = normalize_candidate_id(raw)
    tasks = db.execute(delete(Task).where(Task.candidate_id == cid)).rowcount
    emails = db.execute(delete(EmailRecord).where(EmailRecord.candidate_id == cid)).rowcount
    revs = db.execute(delete(TaskRevision).where(TaskRevision.candidate_id == cid)).rowcount
    db.commit()
    return {
        "ok": True,
        "candidate_id": cid,
        "deleted": {"tasks": tasks, "email_records": emails, "task_revisions": revs},
    }


@router.get("/tasks")
def api_tasks(
    candidate_id: str = Query(default=None),
    run_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Full processing ledger: one item per processed email (including skipped),
    joined with its task and revision history."""
    cid = normalize_candidate_id(candidate_id or settings.CANDIDATE_ID)

    stmt = select(EmailRecord).where(EmailRecord.candidate_id == cid)
    if run_id:
        stmt = stmt.where(EmailRecord.run_id == run_id)
    stmt = stmt.order_by(EmailRecord.received_at.asc())
    records = list(db.scalars(stmt).all())

    task_ids = [r.task_id for r in records if r.task_id]
    tasks_by_id = {}
    revisions_by_task: dict[str, list] = defaultdict(list)
    if task_ids:
        for t in db.scalars(select(Task).where(Task.task_id.in_(task_ids))).all():
            tasks_by_id[t.task_id] = t
        revs = db.scalars(
            select(TaskRevision).where(TaskRevision.task_id.in_(task_ids))
            .order_by(TaskRevision.revision_index.asc())
        ).all()
        for rv in revs:
            revisions_by_task[rv.task_id].append(
                {
                    "revision_index": rv.revision_index,
                    "source_email_id": rv.source_email_id,
                    "changed_fields": rv.changed_fields,
                    "created_at": rv.created_at.isoformat() if rv.created_at else None,
                }
            )

    items = []
    for r in records:
        task = tasks_by_id.get(r.task_id) if r.task_id else None
        revs = revisions_by_task.get(r.task_id, []) if r.task_id else []
        items.append(
            {
                **r.to_meta_dict(),
                "task": task.to_spec_dict() if task else None,
                "revisions": revs,
                "revision_count": len(revs),
            }
        )
    return {"candidate_id": cid, "count": len(items), "items": items}


@router.get("/stats")
def api_stats(
    candidate_id: str = Query(default=None),
    db: Session = Depends(get_db),
):
    cid = normalize_candidate_id(candidate_id or settings.CANDIDATE_ID)
    records = list(db.scalars(select(EmailRecord).where(EmailRecord.candidate_id == cid)).all())

    processed = len(records)
    created = sum(1 for r in records if r.decision == "created")
    updated = sum(1 for r in records if r.decision == "updated")
    skipped = sum(1 for r in records if r.decision == "skipped")
    errored = sum(1 for r in records if r.decision == "error")
    spurious = sum(1 for r in records if r.is_spurious)

    by_category: dict[str, int] = defaultdict(int)
    by_assignee: dict[str, int] = defaultdict(int)
    by_skip_reason: dict[str, int] = defaultdict(int)
    by_run: dict[str, dict] = defaultdict(
        lambda: {"processed": 0, "created": 0, "updated": 0, "skipped": 0}
    )

    for r in records:
        run = r.run_id or "unknown"
        by_run[run]["processed"] += 1
        if r.decision in ("created", "updated"):
            by_run[run][r.decision] += 1
            if r.category:
                by_category[r.category] += 1
            if r.assignee_id:
                by_assignee[r.assignee_id] += 1
        elif r.decision == "skipped":
            by_run[run]["skipped"] += 1
            if r.skip_reason:
                by_skip_reason[r.skip_reason] += 1

    # Latency / token roll-up for the cost/latency-awareness story.
    latencies = [r.latency_ms for r in records if r.latency_ms]
    tokens = sum(r.token_count or 0 for r in records)

    return {
        "candidate_id": cid,
        "processed": processed,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errored,
        "spurious": spurious,
        "spurious_rate": round(spurious / processed, 4) if processed else 0.0,
        "by_category": dict(by_category),
        "by_assignee": dict(by_assignee),
        "by_skip_reason": dict(by_skip_reason),
        "by_run": dict(by_run),
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
        "total_tokens": tokens,
        "run_count": len(by_run),
    }
