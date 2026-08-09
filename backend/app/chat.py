"""POST /api/chat — grounded conversational endpoint (§7.3).

Strict path: question -> Gemini emits a structured query PLAN -> our code
computes numbers from stored ground truth -> Gemini phrases those numbers.
Gemini never produces a number. Numbers come only from computed data, so the
same question asked twice returns identical figures."""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import llm
from .config import normalize_candidate_id, settings
from .db import get_db
from .models import EmailRecord, Task, TaskRevision
from .roster import NAME_BY_ID
from .schemas import ChatIn

router = APIRouter(prefix="/api", tags=["chat"])

SUPPORTED_INTENTS = [
    "count_by_category", "count_by_assignee", "count_skipped_by_reason",
    "list_triage_with_reasons", "spurious_rate", "compound_filter",
    "sum_deal_value", "threads_updated_multiple_times", "action_request", "unknown",
]

PLAN_INSTRUCTION = f"""You translate an ops executive's question about a processed
email batch into a STRUCTURED QUERY PLAN. You do NOT answer with numbers — you only
emit a plan that downstream code will execute against a database.

Return ONLY JSON: {{"intent": "...", "filters": {{...}}, "scope": "current_batch|all"}}

Supported intents: {", ".join(SUPPORTED_INTENTS)}

Guidance:
- count_by_category: filters.category = one of enterprise_rfp|smb_enquiry|marketing|
  alliances|finance|triage, OR a free-text topic (e.g. "gst_refund") if it's not one
  of ours — downstream will correctly return zero for unknown topics.
- count_by_assignee: filters.assignee_id = u_aarti|u_rohit|u_meera|u_karan|u_divya|u_triage.
- count_skipped_by_reason: filters.skip_reason optional (out_of_office|newsletter|vendor_spam).
- compound_filter: any of filters.priority, filters.category, filters.assignee_id,
  filters.confidence_lt (float), filters.confidence_gt (float).
- sum_deal_value: filters.category optional.
- list_triage_with_reasons, spurious_rate, threads_updated_multiple_times: no filters needed.
- action_request: the user is asking to DO something (send an email, create/delete data).
- unknown: the question can't be mapped to stored data.

default scope is current_batch."""

_ACTION_RE = re.compile(
    r"\b(send|email|reply|forward|draft|schedule|call|create a task|delete|assign to|notify|ping)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

def _plan_with_llm(query: str) -> dict | None:
    if not llm.available():
        return None
    try:
        text, _ = llm.generate(PLAN_INSTRUCTION, query, json_mode=True)
        plan = llm.parse_json(text)
        if plan.get("intent") not in SUPPORTED_INTENTS:
            return None
        return plan
    except Exception:  # noqa: BLE001 - fall back to keyword planner
        return None


_KNOWN_CATEGORIES = {"enterprise_rfp", "smb_enquiry", "marketing", "alliances", "finance", "triage"}


def _plan_with_keywords(query: str) -> dict:
    q = query.lower()
    if _ACTION_RE.search(q) and not q.strip().startswith(("how", "what", "which", "show", "list", "did", "count")):
        return {"intent": "action_request", "filters": {}, "scope": "current_batch"}
    if "spurious" in q:
        return {"intent": "spurious_rate", "filters": {}, "scope": "current_batch"}
    if "triage" in q:
        return {"intent": "list_triage_with_reasons", "filters": {}, "scope": "current_batch"}
    if ("updated" in q or "more than once" in q or "twice" in q) and "thread" in q:
        return {"intent": "threads_updated_multiple_times", "filters": {}, "scope": "current_batch"}
    if ("total" in q or "sum" in q or "value" in q) and ("deal" in q or "rfp" in q or "worth" in q):
        return {"intent": "sum_deal_value", "filters": {}, "scope": "current_batch"}
    if ("high" in q and ("low confidence" in q or "confidence" in q)):
        return {"intent": "compound_filter",
                "filters": {"priority": "high", "confidence_lt": 0.5}, "scope": "current_batch"}
    if "skip" in q or "ignored" in q or "spam" in q or "newsletter" in q or "out of office" in q:
        return {"intent": "count_skipped_by_reason", "filters": {}, "scope": "current_batch"}
    for cat in _KNOWN_CATEGORIES:
        if cat.replace("_", " ") in q or cat in q:
            return {"intent": "count_by_category", "filters": {"category": cat}, "scope": "current_batch"}
    if "rfp" in q or "proposal" in q:
        return {"intent": "count_by_category", "filters": {"category": "enterprise_rfp"}, "scope": "current_batch"}
    if "marketing" in q:
        return {"intent": "count_by_category", "filters": {"category": "marketing"}, "scope": "current_batch"}
    for uid in NAME_BY_ID:
        if uid in q or NAME_BY_ID[uid].split()[0].lower() in q:
            return {"intent": "count_by_assignee", "filters": {"assignee_id": uid}, "scope": "current_batch"}
    # topic that isn't one of our categories -> count_by_category with free text (-> zero)
    m = re.search(r"about ([a-z ]+?)(\?|$)", q)
    if m:
        topic = m.group(1).strip().replace(" ", "_")
        return {"intent": "count_by_category", "filters": {"category": topic}, "scope": "current_batch"}
    return {"intent": "unknown", "filters": {}, "scope": "current_batch"}


# ---------------------------------------------------------------------------
# Scope resolution + execution
# ---------------------------------------------------------------------------

def _latest_run_id(db: Session, cid: str) -> str | None:
    return db.scalar(
        select(EmailRecord.run_id).where(EmailRecord.candidate_id == cid)
        .order_by(EmailRecord.processed_at.desc()).limit(1)
    )


def _load_scope(db: Session, cid: str, scope: str, run_id: str | None):
    stmt = select(EmailRecord).where(EmailRecord.candidate_id == cid)
    effective_run = None
    if run_id:
        effective_run = run_id
    elif scope == "current_batch":
        effective_run = _latest_run_id(db, cid)
    if effective_run:
        stmt = stmt.where(EmailRecord.run_id == effective_run)
    records = list(db.scalars(stmt).all())

    task_ids = [r.task_id for r in records if r.task_id]
    tasks_by_id: dict[str, Task] = {}
    if task_ids:
        for t in db.scalars(select(Task).where(Task.task_id.in_(task_ids))).all():
            tasks_by_id[t.task_id] = t
    return records, tasks_by_id, effective_run


def _actionable_tasks(records, tasks_by_id) -> list[Task]:
    seen, out = set(), []
    for r in records:
        if r.task_id and r.task_id in tasks_by_id and r.task_id not in seen:
            seen.add(r.task_id)
            out.append(tasks_by_id[r.task_id])
    return out


def execute(db, cid, plan: dict, records, tasks_by_id) -> dict:
    intent = plan.get("intent", "unknown")
    filters = plan.get("filters") or {}
    tasks = _actionable_tasks(records, tasks_by_id)

    if intent == "count_by_category":
        cat = filters.get("category")
        if not cat:
            counts: dict[str, int] = {}
            for t in tasks:
                counts[t.category] = counts.get(t.category, 0) + 1
            return {"by_category": counts}
        n = sum(1 for t in tasks if t.category == cat)
        return {"category": cat, "count": n, f"{cat}_count": n,
                "is_known_category": cat in _KNOWN_CATEGORIES}

    if intent == "count_by_assignee":
        who = filters.get("assignee_id")
        if not who:
            counts = {}
            for t in tasks:
                counts[t.assignee_id] = counts.get(t.assignee_id, 0) + 1
            return {"by_assignee": counts}
        n = sum(1 for t in tasks if t.assignee_id == who)
        return {"assignee_id": who, "assignee_name": NAME_BY_ID.get(who), "count": n}

    if intent == "count_skipped_by_reason":
        reason = filters.get("skip_reason")
        skipped = [r for r in records if r.decision == "skipped"]
        by_reason: dict[str, int] = {}
        for r in skipped:
            by_reason[r.skip_reason or "unknown"] = by_reason.get(r.skip_reason or "unknown", 0) + 1
        if reason:
            return {"skip_reason": reason, "count": by_reason.get(reason, 0), "by_reason": by_reason}
        return {"skipped_total": len(skipped), "by_reason": by_reason}

    if intent == "list_triage_with_reasons":
        triage = [t for t in tasks if t.assignee_id == "u_triage" or t.category == "triage"]
        return {
            "triage_count": len(triage),
            "triage_task_ids": [t.task_id for t in triage],
            "triage": [
                {"task_id": t.task_id, "title": t.title, "confidence": t.confidence,
                 "description": t.description}
                for t in triage
            ],
        }

    if intent == "spurious_rate":
        processed = len(records)
        spurious = sum(1 for r in records if r.is_spurious)
        return {"spurious_count": spurious, "processed": processed,
                "spurious_rate": round(spurious / processed, 4) if processed else 0.0}

    if intent == "compound_filter":
        matches = []
        for t in tasks:
            if "priority" in filters and t.priority != filters["priority"]:
                continue
            if "category" in filters and t.category != filters["category"]:
                continue
            if "assignee_id" in filters and t.assignee_id != filters["assignee_id"]:
                continue
            if "confidence_lt" in filters and not (t.confidence < float(filters["confidence_lt"])):
                continue
            if "confidence_gt" in filters and not (t.confidence > float(filters["confidence_gt"])):
                continue
            matches.append({"task_id": t.task_id, "title": t.title, "priority": t.priority,
                            "category": t.category, "assignee_id": t.assignee_id,
                            "confidence": t.confidence})
        return {"filters": filters, "match_count": len(matches), "matches": matches}

    if intent == "sum_deal_value":
        cat = filters.get("category")
        pool = [t for t in tasks if (cat is None or t.category == cat)]
        with_value = [t for t in pool if t.deal_value_inr is not None]
        null_count = sum(1 for t in pool if t.deal_value_inr is None)
        total = sum(t.deal_value_inr for t in with_value)
        return {"total_deal_value_inr": total, "tasks_with_value": len(with_value),
                "rows_with_no_stated_value": null_count, "category": cat}

    if intent == "threads_updated_multiple_times":
        task_ids = [t.task_id for t in tasks]
        by_thread: dict[str, int] = {}
        if task_ids:
            revs = db.scalars(
                select(TaskRevision).where(TaskRevision.task_id.in_(task_ids))
            ).all()
            for rv in revs:
                by_thread[rv.thread_id] = by_thread.get(rv.thread_id, 0) + 1
        multi = sorted(th for th, n in by_thread.items() if n >= 2)
        return {"threads_updated_multiple_times": multi, "revision_counts_by_thread": by_thread}

    if intent == "action_request":
        return {}

    return {"note": "unmapped_question"}


# ---------------------------------------------------------------------------
# Phrasing
# ---------------------------------------------------------------------------

def _template_answer(intent: str, data: dict) -> str:
    if intent == "action_request":
        return ("I can't take actions like sending email — I only answer questions about the "
                "emails you've processed. You'll need to send that yourself.")
    if intent == "unknown":
        return ("I don't have that as a stored breakdown, so I can't give you a grounded number "
                "for it. I can report by category, assignee, skip reason, triage items, spurious "
                "rate, deal-value sums, and thread updates.")
    if intent == "count_by_category":
        cat = data.get("category")
        if cat is None:
            return "Task counts by category: " + json.dumps(data.get("by_category", {}))
        n = data.get("count", 0)
        if not data.get("is_known_category", True):
            return f"Zero. I have no emails classified under '{cat}' in this batch."
        return f"{n} task{'s' if n != 1 else ''} were routed as {cat}."
    if intent == "count_by_assignee":
        return f"{data.get('count', 0)} tasks are assigned to {data.get('assignee_name') or data.get('assignee_id')}."
    if intent == "count_skipped_by_reason":
        if "skip_reason" in data:
            return f"{data.get('count', 0)} emails were skipped as {data['skip_reason']}."
        return (f"{data.get('skipped_total', 0)} emails were skipped, correctly generating no task. "
                f"Breakdown: {json.dumps(data.get('by_reason', {}))}.")
    if intent == "list_triage_with_reasons":
        n = data.get("triage_count", 0)
        if n == 0:
            return "Nothing is sitting in triage right now."
        return f"{n} item(s) in triage: " + "; ".join(
            f"{t['title']} (conf {t['confidence']})" for t in data.get("triage", [])
        )
    if intent == "spurious_rate":
        return (f"Spurious rate is {data.get('spurious_rate', 0) * 100:.1f}% "
                f"({data.get('spurious_count', 0)} spurious of {data.get('processed', 0)} processed).")
    if intent == "compound_filter":
        n = data.get("match_count", 0)
        if n == 0:
            return "No tasks match that combination of filters."
        return f"{n} task(s) match: " + ", ".join(m["task_id"] for m in data.get("matches", []))
    if intent == "sum_deal_value":
        return (f"Total stated deal value is ₹{data.get('total_deal_value_inr', 0):,} across "
                f"{data.get('tasks_with_value', 0)} task(s). {data.get('rows_with_no_stated_value', 0)} "
                f"had no stated value and were not counted as zero.")
    if intent == "threads_updated_multiple_times":
        multi = data.get("threads_updated_multiple_times", [])
        if not multi:
            return "No thread was updated more than once."
        return "Threads updated more than once: " + ", ".join(multi)
    return json.dumps(data)


def _phrase_with_llm(query: str, intent: str, data: dict) -> str | None:
    if not llm.available():
        return None
    try:
        instr = (
            "You phrase pre-computed query results into a one or two sentence answer for an ops "
            "executive. Use ONLY the numbers in the data — never invent or recompute. If a count is "
            "zero, say zero plainly. If the intent is action_request, decline politely and say you "
            "only answer questions. If unknown, say you don't store that breakdown."
        )
        payload = json.dumps({"question": query, "intent": intent, "data": data}, ensure_ascii=False)
        text, _ = llm.generate(instr, payload, json_mode=False)
        return (text or "").strip() or None
    except Exception:  # noqa: BLE001
        return None


@router.post("/chat")
def chat(payload: ChatIn = Body(...), db: Session = Depends(get_db)):
    cid = normalize_candidate_id(payload.candidate_id or settings.CANDIDATE_ID)
    query = (payload.query or "").strip()
    if not query:
        return JSONResponse(status_code=400, content={"error": "empty_query"})

    plan = _plan_with_llm(query) or _plan_with_keywords(query)
    records, tasks_by_id, effective_run = _load_scope(
        db, cid, plan.get("scope", "current_batch"), payload.run_id
    )
    data = execute(db, cid, plan, records, tasks_by_id)

    answer = _phrase_with_llm(query, plan["intent"], data) or _template_answer(plan["intent"], data)

    return {
        "answer": answer,
        "supporting_data": data,
        "query": {"intent": plan["intent"], "filters": plan.get("filters", {}),
                  "scope": plan.get("scope", "current_batch"), "run_id": effective_run},
    }
