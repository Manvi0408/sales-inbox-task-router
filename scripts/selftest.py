#!/usr/bin/env python3
"""Run the three grading scenarios against a deployed (or local) backend and
print a report. Stdlib only — no dependencies.

Usage:
    python scripts/selftest.py https://your-backend.onrender.com
    BACKEND_URL=http://localhost:8000 python scripts/selftest.py

Scenarios:
  1. Accuracy         — POST the 12 worked examples to /ingest, read GET /tasks,
                        align on source_email_id, bucket correct/misrouted/missed/spurious.
  2. Idempotency      — re-POST the identical batch; task count must not change.
  3. Thread reconcile — POST a reply on an existing thread + a brand-new thread;
                        count grows only by the new thread; the reply shows as an update.
Plus: the enum-400 shape and the two chat traps (zero-count + out-of-scope).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BACKEND_URL", "http://localhost:8000")).rstrip("/")
CID = os.environ.get("CANDIDATE_ID", "manviitnd0408@gmail.com")
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "worked_examples.json"

PASS, FAIL = 0, 0


def _req(method: str, path: str, body: dict | None = None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}   {extra}")


def load_examples():
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    emails = [{k: v for k, v in e.items() if k != "expected"} for e in data["emails"]]
    expected = {e["email_id"]: e["expected"] for e in data["emails"]}
    return emails, expected


def main():
    print(f"Backend: {BASE}\ncandidate_id: {CID}\n")

    emails, expected = load_examples()

    # ---- Scenario 1: accuracy ----
    print("== Scenario 1 — accuracy ==")
    st, res = _req("POST", "/ingest", {"candidate_id": CID, "emails": emails})
    check("/ingest returns 200", st == 200, f"got {st}")
    print(f"    ingest: {json.dumps({k: res.get(k) for k in ('processed','tasks_created','tasks_updated','skipped')})}")

    st, tasks = _req("GET", f"/tasks?candidate_id={CID}")
    check("GET /tasks returns a list", isinstance(tasks, list), str(type(tasks)))
    by_source = {t["source_email_id"]: t for t in tasks} if isinstance(tasks, list) else {}

    correct = misrouted = missed = spurious = 0
    for eid, exp in expected.items():
        t = by_source.get(eid)
        if exp["decision"] == "skipped":
            if t is not None:
                spurious += 1
                print(f"    spurious: {eid} created a task but should be skipped")
        elif exp["decision"] in ("created", "updated"):
            if t is None and eid != "em_ex10":  # ex10 updates ex01, no own task
                missed += 1
                print(f"    missed: {eid}")
            elif t is not None:
                if t["assignee_id"] == exp.get("assignee_id"):
                    correct += 1
                else:
                    misrouted += 1
                    print(f"    misrouted: {eid} -> {t['assignee_id']} (expected {exp.get('assignee_id')})")
    print(f"    correct={correct} misrouted={misrouted} missed={missed} spurious={spurious}")
    check("no spurious tasks (auto-reply/spam/newsletter skipped)", spurious == 0, f"spurious={spurious}")
    check("majority correctly routed", correct >= 6, f"correct={correct}")

    # ---- Scenario 2: idempotency ----
    print("== Scenario 2 — idempotency ==")
    _, before = _req("GET", f"/tasks?candidate_id={CID}")
    st, res2 = _req("POST", "/ingest", {"candidate_id": CID, "emails": emails})
    _, after = _req("GET", f"/tasks?candidate_id={CID}")
    check("task count unchanged on re-post", len(before) == len(after), f"{len(before)} -> {len(after)}")
    check("re-post created 0 tasks", res2.get("tasks_created") == 0, f"created={res2.get('tasks_created')}")

    # ---- Scenario 3: thread reconciliation ----
    print("== Scenario 3 — thread reconciliation ==")
    _, base_tasks = _req("GET", f"/tasks?candidate_id={CID}")
    reply_batch = [
        {  # reply on an existing thread (th_ex02) -> should UPDATE, not create
            "email_id": "em_reply_02", "thread_id": "th_ex02", "message_index": 1,
            "from_name": "Ankit Bose", "from_email": "ankit@railyardlogistics.in",
            "subject": "RE: Quick demo request", "is_reply": True,
            "body": "Following up — we'd like to move fast now, can we demo by this Friday?",
            "received_at": "2026-08-06T09:00:00+05:30",
        },
        {  # brand-new thread -> should CREATE exactly one task
            "email_id": "em_new_99", "thread_id": "th_new_99", "message_index": 0,
            "from_name": "Latha Menon", "from_email": "latha@brightpath.co.in",
            "subject": "Demo request for 20-seat team", "is_reply": False,
            "body": "Hi, we're a 20-person team and would love a product demo. No urgency.",
            "received_at": "2026-08-06T10:00:00+05:30",
        },
    ]
    st, res3 = _req("POST", "/ingest", {"candidate_id": CID, "emails": reply_batch})
    _, after3 = _req("GET", f"/tasks?candidate_id={CID}")
    grew_by = len(after3) - len(base_tasks)
    check("count grew by exactly 1 (new thread only)", grew_by == 1, f"grew_by={grew_by}")
    check("reply reported as an update", res3.get("tasks_updated", 0) >= 1, f"updated={res3.get('tasks_updated')}")
    check("reply did not create a second task on th_ex02",
          len([t for t in after3 if t["thread_id"] == "th_ex02"]) == 1)

    # ---- Enum 400 shape ----
    print("== Enum validation ==")
    st, body = _req("POST", "/tasks", {
        "candidate_id": CID, "source_email_id": "em_enumcheck", "thread_id": "th_x",
        "title": "x", "assignee_id": "Aarti", "category": "enterprise_rfp",
        "priority": "high", "due_date": None, "deal_value_inr": None,
        "company_name": None, "confidence": 0.9,
    })
    check("bad enum -> 400", st == 400, f"got {st}")
    check("exact invalid_enum_value shape", body == {
        "error": "invalid_enum_value", "field": "assignee_id", "received": "Aarti",
        "allowed": ["u_aarti", "u_rohit", "u_meera", "u_karan", "u_divya", "u_triage"]}, json.dumps(body))

    # ---- Chat traps ----
    print("== Chat grounding ==")
    _, gst = _req("POST", "/api/chat", {"candidate_id": CID, "query": "How many emails were about GST refunds?"})
    check("GST-refund answer says zero", "zero" in gst.get("answer", "").lower() or "0" in gst.get("answer", ""),
          gst.get("answer"))
    _, act = _req("POST", "/api/chat", {"candidate_id": CID, "query": "Send Aarti an email about the RFP"})
    ans = act.get("answer", "").lower()
    check("action request declined", any(s in ans for s in ("can't", "cannot", "only answer", "don't")), act.get("answer"))
    _, a1 = _req("POST", "/api/chat", {"candidate_id": CID, "query": "how many enterprise_rfp tasks?"})
    _, a2 = _req("POST", "/api/chat", {"candidate_id": CID, "query": "how many enterprise_rfp tasks?"})
    check("same question -> identical supporting_data", a1.get("supporting_data") == a2.get("supporting_data"))

    print(f"\nRESULT: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
