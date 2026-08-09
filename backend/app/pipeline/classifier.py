"""Stage 4 — LLM classification (Groq or Gemini) with retries + a pure-rules
fallback.

classify() never raises for LLM problems: on repeated failure it degrades to a
deterministic classifier (confidence <= 0.35) so an email is never dropped."""
from __future__ import annotations

import time
from datetime import date

from .. import llm
from ..enums import ASSIGNEE_VALUES, CATEGORY_VALUES, PRIORITY_VALUES
from .detectors import is_invoice
from .prompt import build_user_prompt, system_instruction
from .types import Classification

_system_cache: str | None = None


def _system() -> str:
    global _system_cache
    if _system_cache is None:
        _system_cache = system_instruction()
    return _system_cache


def _coerce_enum(value, allowed: list[str], default: str) -> str:
    return value if value in allowed else default


def _parse_iso_date(value) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _as_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _build_from_llm(data: dict, *, money, due, cleaned_body: str, subject: str) -> Classification:
    is_actionable = bool(data.get("is_actionable", True))
    skip_reason = data.get("skip_reason") or None

    category = _coerce_enum(data.get("category"), CATEGORY_VALUES, "triage")
    assignee = _coerce_enum(data.get("assignee_id"), ASSIGNEE_VALUES, "u_triage")
    priority = _coerce_enum(data.get("priority"), PRIORITY_VALUES, "medium")

    company = data.get("company_name")
    if isinstance(company, str) and not company.strip():
        company = None

    try:
        conf = float(data.get("confidence", 0.6))
    except (TypeError, ValueError):
        conf = 0.6
    conf = max(0.0, min(1.0, conf))

    title = (data.get("title") or subject or "Email task").strip()[:200]
    description = (data.get("description") or cleaned_body[:500]).strip()

    # Deterministic parser is authoritative; the LLM's value is used only as a
    # fallback when the parser found nothing (catches phrasings we don't regex).
    final_due = due if due is not None else _parse_iso_date(data.get("due_date"))
    final_money = money if money is not None else _as_int(data.get("deal_value_inr"))

    return Classification(
        is_actionable=is_actionable,
        skip_reason=skip_reason if not is_actionable else None,
        category=category,
        assignee_id=assignee,
        priority=priority,
        due_date=final_due,
        deal_value_inr=final_money,
        company_name=company,
        confidence=conf,
        reasoning=(data.get("reasoning") or "").strip()[:400],
        direction_of_intent=_coerce_enum(
            data.get("direction_of_intent"),
            ["inbound_buyer", "outbound_seller", "informational"],
            "inbound_buyer",
        ),
        title=title,
        description=description,
        llm_proposed_assignee=assignee,
        source="llm",
    )


# ---------------------------------------------------------------------------
# Pure-rules fallback — used when the LLM is unavailable or keeps failing.
# ---------------------------------------------------------------------------

_KEYWORDS = [
    ("finance", "u_divya", ["invoice", "purchase order", "payment", "gst", "po-", "overdue", "billing"]),
    ("marketing", "u_meera", ["sponsor", "webinar", "conference", "event", "pr ", "media", "content collaborat"]),
    ("alliances", "u_karan", ["reseller", "channel partner", "integration partner", "partnership", "reselling"]),
    ("enterprise_rfp", "u_aarti", ["rfp", "rfi", "tender", "proposal", "bid"]),
    ("smb_enquiry", "u_rohit", ["demo", "trial", "pricing", "enquiry", "inquiry", "evaluate"]),
]


def rules_only_classify(*, subject: str, cleaned_body: str, signals: dict, money, due) -> Classification:
    low = f"{subject}\n{cleaned_body}".lower()

    if signals.get("auto_reply"):
        return _skip("out_of_office", "informational")
    if signals.get("newsletter"):
        return _skip("newsletter", "informational")
    if signals.get("outbound_spam"):
        return _skip("vendor_spam", "outbound_seller")

    category, assignee = "triage", "u_triage"
    for cat, who, kws in _KEYWORDS:
        if any(k in low for k in kws):
            category, assignee = cat, who
            break

    if is_invoice(cleaned_body):
        category, assignee, money = "finance", "u_divya", None

    return Classification(
        is_actionable=True,
        category=category,
        assignee_id=assignee,
        priority="medium",
        due_date=due,
        # Keep a stated amount for every category except finance (invoice ≠ deal),
        # matching the LLM path and §6 Example 4 (marketing sponsorship keeps its price).
        deal_value_inr=None if category == "finance" else money,
        company_name=None,
        confidence=0.35 if category != "triage" else 0.25,
        reasoning="LLM unavailable — deterministic keyword fallback.",
        direction_of_intent="inbound_buyer",
        title=(subject or "Email task")[:200],
        description=cleaned_body[:500],
        llm_proposed_assignee=None,
        rules_fired=["FALLBACK_NO_LLM"],
        source="fallback",
    )


def _skip(reason: str, direction: str) -> Classification:
    return Classification(
        is_actionable=False,
        skip_reason=reason,
        category="triage",
        assignee_id="u_triage",
        confidence=0.3,
        reasoning=f"Deterministic fallback: {reason}.",
        direction_of_intent=direction,
        rules_fired=["FALLBACK_NO_LLM"],
        source="fallback",
    )


def classify(
    *,
    subject: str,
    cleaned_body: str,
    received_at: str,
    signals: dict,
    money: int | None,
    due: date | None,
    is_reply: bool,
) -> tuple[Classification, int, int]:
    """Return (classification, latency_ms, token_count). Falls back to rules on
    any LLM failure, and if no API key is configured."""
    start = time.perf_counter()

    if not llm.available():
        c = rules_only_classify(
            subject=subject, cleaned_body=cleaned_body, signals=signals, money=money, due=due
        )
        return c, int((time.perf_counter() - start) * 1000), 0

    try:
        user_prompt = build_user_prompt(
            subject=subject, cleaned_body=cleaned_body, received_at=received_at,
            signals=signals, money=money, due=due, is_reply=is_reply,
        )
        text, tokens = llm.generate(_system(), user_prompt, json_mode=True)
        data = llm.parse_json(text)
        c = _build_from_llm(data, money=money, due=due, cleaned_body=cleaned_body, subject=subject)
        return c, int((time.perf_counter() - start) * 1000), tokens
    except Exception:  # noqa: BLE001 - degrade gracefully, never drop the email
        c = rules_only_classify(
            subject=subject, cleaned_body=cleaned_body, signals=signals, money=money, due=due
        )
        return c, int((time.perf_counter() - start) * 1000), 0
