"""Stage 5 — deterministic overrides, applied AFTER the LLM. Each rule that
fires is recorded in rules_fired. Order matters: R4 (no-task) is checked first,
then PSU, then value routing, then invoice + deadline adjustments."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .types import Classification

IST = ZoneInfo("Asia/Kolkata")

VALUE_THRESHOLD = 1_000_000  # ₹10,00,000

# Categories where a stated deal value should drive Aarti/Rohit routing.
SALES_CATEGORIES = {"enterprise_rfp", "smb_enquiry"}


def _within_72h(due, received_at: datetime | None) -> bool:
    if due is None or received_at is None:
        return False
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=IST)
    received_ist = received_at.astimezone(IST)
    # Treat the deadline as end-of-day IST for the 72h window.
    due_dt = datetime(due.year, due.month, due.day, 23, 59, 59, tzinfo=IST)
    return received_ist <= due_dt <= received_ist + timedelta(hours=72)


def apply_rules(
    c: Classification,
    *,
    signals: dict,
    received_at: datetime | None,
) -> Classification:
    """Mutate and return the classification with deterministic overrides applied.
    Deal value is read from the classification (parser value already merged in)."""
    fired: list[str] = list(c.rules_fired)
    money = c.deal_value_inr

    # R4_NO_TASK — auto-reply, newsletter, or outbound vendor spam => no task.
    if signals.get("auto_reply"):
        c.is_actionable = False
        c.skip_reason = "out_of_office"
        fired.append("R4_NO_TASK")
    elif signals.get("newsletter"):
        c.is_actionable = False
        c.skip_reason = "newsletter"
        fired.append("R4_NO_TASK")
    elif signals.get("outbound_spam") and c.direction_of_intent == "outbound_seller":
        c.is_actionable = False
        c.skip_reason = "vendor_spam"
        fired.append("R4_NO_TASK")

    if not c.is_actionable:
        c.rules_fired = fired
        return c

    # R3_PSU — PSU / government tender => Aarti + enterprise_rfp, beats value.
    if signals.get("psu"):
        if c.assignee_id != "u_aarti" or c.category != "enterprise_rfp":
            c.override_applied = True
        c.assignee_id = "u_aarti"
        c.category = "enterprise_rfp"
        fired.append("R3_PSU")

    # R_INVOICE_NOT_DEAL — invoice/PO amount is never a deal value.
    if signals.get("invoice") or c.category == "finance":
        if signals.get("invoice") and c.category not in {"finance"}:
            # Strong invoice signal but LLM missed it — nudge to finance.
            c.category = "finance"
            c.assignee_id = "u_divya"
            c.override_applied = True
        c.deal_value_inr = None
        fired.append("R_INVOICE_NOT_DEAL")

    # R_VALUE — deal value routing, only for genuine sales enquiries with a
    # stated value. Never for marketing/alliances/finance.
    if c.category in SALES_CATEGORIES and money is not None and not signals.get("psu"):
        proposed = "u_aarti" if money > VALUE_THRESHOLD else "u_rohit"
        if money > VALUE_THRESHOLD:
            # Above threshold is enterprise-flavoured.
            if c.category == "smb_enquiry":
                c.category = "enterprise_rfp"
        if c.assignee_id != proposed:
            c.override_applied = True
        c.assignee_id = proposed
        fired.append("R_VALUE")

    # R1_DEADLINE_72H — deadline within 72h of received_at => high priority.
    if _within_72h(c.due_date, received_at):
        if c.priority != "high":
            c.override_applied = True
        c.priority = "high"
        fired.append("R1_DEADLINE_72H")

    c.rules_fired = fired
    return c
