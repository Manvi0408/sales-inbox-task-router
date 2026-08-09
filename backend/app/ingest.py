"""POST /ingest — synchronous. Classification (Stages 1-5) runs concurrently
with a capped thread pool; DB writes (Stage 6) run sequentially in received_at
order so a thread's original always lands before its reply."""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from . import task_service
from .config import normalize_candidate_id, settings
from .db import get_db
from .models import EmailRecord
from .pipeline import classifier, rules
from .pipeline.detectors import detect_all
from .pipeline.normalize import clean_body
from .pipeline.parsers import parse_deadline, parse_money
from .pipeline.types import Classification
from .schemas import EmailIn, IngestIn, TaskCreateIn

router = APIRouter(tags=["ingest"])

SKIP_SIGNAL_KEYS = ("auto_reply", "newsletter", "outbound_spam")


@dataclass
class Prepared:
    email: EmailIn
    received_dt: datetime
    cleaned: str
    signals: dict
    classification: Classification
    latency_ms: int = 0
    token_count: int = 0
    errored: bool = False
    error_msg: str | None = None
    extra_rules: list[str] = field(default_factory=list)


def _parse_received(value: str | None) -> datetime:
    if value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _prepare(email: EmailIn) -> Prepared:
    """Stages 1-5 for a single email — pure/LLM, no DB. Safe to run in a thread."""
    received_dt = _parse_received(email.received_at)
    cleaned = clean_body(email.body or "")
    subject = email.subject or ""
    signals = detect_all(subject, cleaned, email.from_email or "")
    money = parse_money(cleaned)
    due = parse_deadline(cleaned, received_dt)

    try:
        c, latency, tokens = classifier.classify(
            subject=subject,
            cleaned_body=cleaned,
            received_at=email.received_at or received_dt.isoformat(),
            signals=signals,
            money=money,
            due=due,
            is_reply=bool(email.is_reply),
        )
        c = rules.apply_rules(c, signals=signals, received_at=received_dt)
        return Prepared(email, received_dt, cleaned, signals, c, latency, tokens)
    except Exception as exc:  # noqa: BLE001 - should be rare; classify already guards
        c = Classification(
            is_actionable=True, category="triage", assignee_id="u_triage",
            confidence=0.2, reasoning=f"pipeline error: {exc}",
            rules_fired=["FALLBACK_NO_LLM"], source="fallback",
            title=(email.subject or "Email task"), description=cleaned[:500],
        )
        return Prepared(email, received_dt, cleaned, signals, c, 0, 0,
                        errored=True, error_msg=str(exc))


def _upsert_email_record(db: Session, cid: str, p: Prepared, *, decision: str,
                         task_id: str | None, run_id: str, is_spurious: bool) -> None:
    e = p.email
    c = p.classification
    rec = db.get(EmailRecord, (cid, e.email_id))
    if rec is None:
        rec = EmailRecord(candidate_id=cid, email_id=e.email_id)
        db.add(rec)
    rec.thread_id = e.thread_id
    rec.message_index = e.message_index
    rec.from_name = e.from_name
    rec.from_email = e.from_email
    rec.subject = e.subject
    rec.body = e.body
    rec.cleaned_body = p.cleaned
    rec.received_at = p.received_dt
    rec.attachments = e.attachments
    rec.is_reply = bool(e.is_reply)
    rec.decision = decision
    rec.skip_reason = c.skip_reason
    rec.category = c.category
    rec.assignee_id = c.assignee_id if c.is_actionable else None
    rec.confidence = c.confidence
    rec.reasoning = c.reasoning
    rec.direction_of_intent = c.direction_of_intent
    rec.rules_fired = c.rules_fired
    rec.llm_proposed_assignee = c.llm_proposed_assignee
    rec.override_applied = c.override_applied
    rec.is_spurious = is_spurious
    rec.task_id = task_id
    rec.run_id = run_id
    rec.latency_ms = p.latency_ms
    rec.token_count = p.token_count
    rec.processed_at = datetime.now(timezone.utc)


def _changes_from(c: Classification) -> dict:
    return {
        "title": c.title,
        "description": c.description,
        "assignee_id": c.assignee_id,
        "category": c.category,
        "priority": c.priority,
        "due_date": c.due_date,
        "deal_value_inr": c.deal_value_inr,
        "company_name": c.company_name,
        "confidence": c.confidence,
    }


def process_batch(db: Session, candidate_id: str, emails: list[EmailIn],
                  run_id: str | None = None) -> dict:
    cid = normalize_candidate_id(candidate_id)
    run_id = run_id or str(uuid.uuid4())

    # Sort by received_at so originals precede replies within a thread.
    ordered = sorted(emails, key=lambda e: _parse_received(e.received_at))

    # Stage 1-5 concurrently (capped).
    workers = max(1, settings.gemini_max_concurrency)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        prepared: list[Prepared] = list(pool.map(_prepare, ordered))

    created = updated = skipped = 0
    errors: list[dict] = []

    # Stage 6 — sequential writes in received_at order.
    for p in prepared:
        e = p.email
        c = p.classification
        try:
            if not c.is_actionable:
                _upsert_email_record(db, cid, p, decision="skipped", task_id=None,
                                     run_id=run_id, is_spurious=False)
                skipped += 1
                continue

            # Replay: this exact source_email already produced a task -> neither.
            existing_source = task_service.find_by_source(db, cid, e.email_id)
            if existing_source is not None:
                _upsert_email_record(db, cid, p, decision="created",
                                     task_id=existing_source.task_id, run_id=run_id,
                                     is_spurious=False)
                continue

            # Thread update path.
            thread_task = task_service.find_by_thread(db, cid, e.thread_id)
            spurious = any(p.signals.get(k) for k in SKIP_SIGNAL_KEYS)
            if thread_task is not None:
                task_service.apply_update(db, thread_task, _changes_from(c),
                                          source_email_id=e.email_id)
                _upsert_email_record(db, cid, p, decision="updated",
                                     task_id=thread_task.task_id, run_id=run_id,
                                     is_spurious=spurious)
                updated += 1
                continue

            # Create path.
            data = TaskCreateIn(
                candidate_id=cid, source_email_id=e.email_id, thread_id=e.thread_id,
                title=c.title, description=c.description, assignee_id=c.assignee_id,
                category=c.category, priority=c.priority, due_date=c.due_date,
                deal_value_inr=c.deal_value_inr, company_name=c.company_name,
                confidence=c.confidence,
            )
            task, was_created = task_service.create_task(db, data)
            _upsert_email_record(db, cid, p, decision="created", task_id=task.task_id,
                                 run_id=run_id, is_spurious=spurious)
            if was_created:
                created += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            errors.append({"email_id": e.email_id, "error": str(exc)})
            try:
                _upsert_email_record(db, cid, p, decision="error", task_id=None,
                                     run_id=run_id, is_spurious=False)
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
            continue

    db.commit()
    return {
        "processed": len(emails),
        "tasks_created": created,
        "tasks_updated": updated,
        "skipped": skipped,
        "errors": errors,
        "run_id": run_id,
    }


@router.post("/ingest")
def ingest(payload: dict = Body(...), db: Session = Depends(get_db)):
    try:
        data = IngestIn.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=400, content={"error": "invalid_payload", "detail": str(exc)})

    if len(data.emails) > 100:
        return JSONResponse(status_code=400,
                            content={"error": "batch_too_large", "max": 100, "received": len(data.emails)})

    result = process_batch(db, data.candidate_id or settings.CANDIDATE_ID, data.emails, data.run_id)
    return JSONResponse(status_code=200, content=result)
