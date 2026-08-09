#!/usr/bin/env python3
"""Evaluate routing against the hand-labelled fixtures/eval_set.json.

Ingests the set, reads back the processing ledger from /api/tasks, aligns to the
gold labels, and prints:
  - a confusion-style bucket count (correct / misrouted / missed / spurious),
  - precision / recall / F1 per category,
  - a confidence-calibration table (accuracy per confidence bucket).

Usage:
    python scripts/eval.py https://your-backend.onrender.com
    BACKEND_URL=http://localhost:8000 python scripts/eval.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BACKEND_URL", "http://localhost:8000")).rstrip("/")
CID = os.environ.get("CANDIDATE_ID", "manviitnd0408@gmail.com")
EVAL = Path(__file__).resolve().parent.parent / "fixtures" / "eval_set.json"
CATEGORIES = ["enterprise_rfp", "smb_enquiry", "marketing", "alliances", "finance", "triage"]


def _post(path, body):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def _get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=120) as r:
        return json.loads(r.read().decode())


def main():
    data = json.loads(EVAL.read_text(encoding="utf-8"))
    rows = data["emails"]
    emails = [{k: v for k, v in e.items() if k != "gold"} for e in rows]
    gold = {e["email_id"]: e["gold"] for e in rows}

    # ingest in chunks of 100 sharing one run
    import uuid
    run_id = str(uuid.uuid4())
    for i in range(0, len(emails), 100):
        _post("/ingest", {"candidate_id": CID, "emails": emails[i:i + 100], "run_id": run_id})

    ledger = _get(f"/api/tasks?candidate_id={CID}&run_id={run_id}")["items"]
    by_id = {it["email_id"]: it for it in ledger}

    # --- buckets ---
    correct = misrouted = missed = spurious = 0
    # per-category prediction/gold tallies for P/R/F1 (on actionable emails)
    tp = {c: 0 for c in CATEGORIES}
    fp = {c: 0 for c in CATEGORIES}
    fn = {c: 0 for c in CATEGORIES}
    calib = {"0.9-1.0": [0, 0], "0.7-0.9": [0, 0], "0.5-0.7": [0, 0], "<0.5": [0, 0]}

    def bucket(conf):
        if conf >= 0.9:
            return "0.9-1.0"
        if conf >= 0.7:
            return "0.7-0.9"
        if conf >= 0.5:
            return "0.5-0.7"
        return "<0.5"

    for eid, g in gold.items():
        it = by_id.get(eid)
        pred_decision = it["decision"] if it else "missing"
        if g["decision"] == "skipped":
            if it and it["decision"] != "skipped" and it.get("task_id"):
                spurious += 1
            continue
        # actionable gold
        if it is None or it.get("task_id") is None:
            missed += 1
            fn[g["category"]] += 1
            continue
        pred_cat = it["category"]
        pred_assignee = it["assignee_id"]
        # routing correctness on assignee
        correct_here = pred_assignee == g["assignee"]
        if correct_here:
            correct += 1
        else:
            misrouted += 1
        # category P/R/F1
        if pred_cat == g["category"]:
            tp[g["category"]] += 1
        else:
            fp[pred_cat] = fp.get(pred_cat, 0) + 1
            fn[g["category"]] += 1
        # calibration keyed on assignee correctness
        c = it.get("confidence") or 0.0
        b = bucket(c)
        calib[b][1] += 1
        if correct_here:
            calib[b][0] += 1

    total_actionable = sum(1 for g in gold.values() if g["decision"] != "skipped")
    print(f"Backend: {BASE}")
    print(f"Eval set: {len(rows)} emails ({total_actionable} actionable, {len(rows) - total_actionable} noise)\n")
    print("== Buckets ==")
    print(f"  correct   = {correct}")
    print(f"  misrouted = {misrouted}")
    print(f"  missed    = {missed}")
    print(f"  spurious  = {spurious}   (lower is better; 0 is the goal)\n")

    print("== Precision / Recall / F1 by category ==")
    print(f"  {'category':16} {'P':>6} {'R':>6} {'F1':>6}  (tp/fp/fn)")
    macro = []
    for c in CATEGORIES:
        p = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) else 0.0
        r = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
        macro.append(f1)
        print(f"  {c:16} {p:6.2f} {r:6.2f} {f1:6.2f}  ({tp[c]}/{fp[c]}/{fn[c]})")
    print(f"  {'macro-F1':16} {'':6} {'':6} {sum(macro)/len(macro):6.2f}\n")

    print("== Confidence calibration (assignee accuracy per bucket) ==")
    print(f"  {'bucket':10} {'n':>4} {'accuracy':>9}")
    for b, (ok, n) in calib.items():
        acc = ok / n if n else 0.0
        print(f"  {b:10} {n:>4} {acc:>9.2f}")


if __name__ == "__main__":
    main()
