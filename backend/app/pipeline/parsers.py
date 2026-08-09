"""Stage 3 — cheap deterministic parsers. Money and dates. These run before the
LLM and are passed in as facts; the LLM is instructed not to override them.

Rule of thumb: return None when nothing is clearly stated. Never guess."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------

_MULTIPLIERS = {
    "cr": 10_000_000,
    "crore": 10_000_000,
    "crores": 10_000_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "lac": 100_000,
    "lacs": 100_000,
    "l": 100_000,
    "k": 1_000,
}

# currency-led, e.g. "Rs. 25 lakhs", "₹4,00,000", "INR 25L", "Rs 6,50,000"
_CURRENCY_RE = re.compile(
    r"(?:₹|rs\.?|inr)\s*([\d][\d,]*(?:\.\d+)?)\s*(cr(?:ores?)?|lakhs?|lacs?|l|k)?\b",
    re.IGNORECASE,
)
# unit-led without currency, e.g. "1.2 cr", "25L", "25 lakhs"
_UNIT_RE = re.compile(
    r"\b([\d][\d,]*(?:\.\d+)?)\s*(cr(?:ores?)?|lakhs?|lacs?|l)\b",
    re.IGNORECASE,
)
# bare large integer, e.g. "2500000"
_BARE_INT_RE = re.compile(r"\b(\d{6,})\b")


def _to_int(num_str: str, unit: str | None) -> int | None:
    try:
        value = float(num_str.replace(",", ""))
    except ValueError:
        return None
    if unit:
        mult = _MULTIPLIERS.get(unit.lower())
        if mult:
            value *= mult
    return int(round(value))


def parse_money(text: str) -> int | None:
    """Extract a stated INR amount, or None. Lakh=1e5, crore=1e7.

    Preference: currency-led match, then unit-led, then a bare 6+ digit integer.
    Returns the first strong match found (callers clean quoted text first)."""
    if not text:
        return None

    m = _CURRENCY_RE.search(text)
    if m:
        val = _to_int(m.group(1), m.group(2))
        if val is not None:
            return val

    m = _UNIT_RE.search(text)
    if m:
        val = _to_int(m.group(1), m.group(2))
        if val is not None:
            return val

    m = _BARE_INT_RE.search(text)
    if m:
        return _to_int(m.group(1), None)

    return None


# ---------------------------------------------------------------------------
# Dates / deadlines
# ---------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DMY_RE = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b")
_DAY_MONTH_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
    r"(?:\s+(\d{4}))?\b",
    re.IGNORECASE,
)
_MONTH_DAY_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b",
    re.IGNORECASE,
)
_WITHIN_RE = re.compile(r"\bwithin\s+(\d{1,3})\s*(hours?|hrs?|days?)\b", re.IGNORECASE)
_IN_N_RE = re.compile(r"\bin\s+(\d{1,3})\s*(hours?|hrs?|days?)\b", re.IGNORECASE)

# Vague phrases that are explicitly NOT deadlines.
_VAGUE_RE = re.compile(
    r"\b(sometime|some time|next week|next month|soon|asap|tbd|shortly|in the coming|"
    r"whenever|no rush|no hurry)\b",
    re.IGNORECASE,
)


def _as_ist(received_at: datetime | None) -> datetime:
    if received_at is None:
        return datetime.now(IST)
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=IST)
    return received_at.astimezone(IST)


def _safe_date(y: int, mo: int, d: int) -> date | None:
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def parse_deadline(text: str, received_at: datetime | None) -> date | None:
    """Resolve a stated deadline to a date (IST), relative to received_at.
    Vague phrases ('sometime next week', 'soon') return None."""
    if not text:
        return None
    base = _as_ist(received_at)

    # 1) Explicit absolute dates (most specific first).
    m = _ISO_RE.search(text)
    if m:
        d = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            return d

    m = _DMY_RE.search(text)
    if m:
        # dayfirst: DD-MM-YYYY (e.g. 03-08-2026 -> 3 Aug 2026)
        d = _safe_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if d:
            return d

    m = _DAY_MONTH_RE.search(text)
    if m:
        year = int(m.group(3)) if m.group(3) else base.year
        d = _safe_date(year, _MONTHS[m.group(2).lower()], int(m.group(1)))
        if d:
            return d

    m = _MONTH_DAY_RE.search(text)
    if m:
        year = int(m.group(3)) if m.group(3) else base.year
        d = _safe_date(year, _MONTHS[m.group(1).lower()], int(m.group(2)))
        if d:
            return d

    # 2) Relative windows.
    m = _WITHIN_RE.search(text) or _IN_N_RE.search(text)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        delta = timedelta(hours=n) if unit.startswith(("hour", "hr")) else timedelta(days=n)
        return (base + delta).date()

    low = text.lower()
    if "day after tomorrow" in low:
        return (base + timedelta(days=2)).date()
    if "tomorrow" in low:
        return (base + timedelta(days=1)).date()
    if re.search(r"\b(today|eod|end of day|by end of day|cob)\b", low) and not _VAGUE_RE.search(low):
        return base.date()

    # 3) "by <weekday>"
    m = re.search(r"\bby\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", low)
    if m:
        target = _WEEKDAYS[m.group(1)]
        ahead = (target - base.weekday()) % 7
        return (base + timedelta(days=ahead)).date()

    # 4) Bare ordinal day ("...review 20th ko hai") — only when a deadline cue is
    # present, to avoid turning ordinals in ordinary prose into fake deadlines.
    _cue = re.compile(
        r"\b(by|due|deadline|before|submit|submission|last\s*date|review|confirm|"
        r"close|closes|closing|expect|ko\s*hai|tak|need it)\b",
        re.IGNORECASE,
    )
    if _cue.search(text):
        m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\b", text)
        if m:
            day = int(m.group(1))
            cand = _safe_date(base.year, base.month, day)
            if cand is None:
                return None
            if cand < base.date():  # already passed this month -> next month
                nm = base.month + 1
                ny = base.year + (1 if nm > 12 else 0)
                nm = 1 if nm > 12 else nm
                cand = _safe_date(ny, nm, day)
            return cand

    return None
