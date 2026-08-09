"""Stage 3 deterministic detectors: PSU/government, auto-reply, newsletter,
invoice, and outbound-vendor-spam signals. All return booleans passed to the
LLM as hints and consumed by the rules engine."""
from __future__ import annotations

import re

_PSU_NAMES = [
    "bhel", "bharat heavy electricals", "ongc", "oil and natural gas",
    "ntpc", "sail", "steel authority", "gail", "iocl", "indian oil",
    "bpcl", "bharat petroleum", "hpcl", "hindustan petroleum",
    "coal india", "bel", "bharat electronics", "hal", "hindustan aeronautics",
    "isro", "drdo", "indian railways", "irctc", "nhpc", "powergrid",
    "nmdc", "rites", "bsnl", "mtnl", "lic",
]
_PSU_PATTERNS = [
    r"\.gov\.in", r"\.nic\.in", r"tender\s*notice\s*no", r"e-?procurement",
    r"\bemd\b", r"bid\s*submission", r"gem\s*portal", r"public\s*sector",
]

_AUTOREPLY_PHRASES = [
    "out of office", "auto-reply", "automatic reply", "autoreply",
    "i am currently away", "i'm currently away", "away from my desk",
    "on leave until", "on vacation", "annual leave", "return to office",
    "limited access to email", "will respond when i return",
]

_NEWSLETTER_PHRASES = [
    "unsubscribe", "view in browser", "view this email in your browser",
    "you're receiving this because", "you are receiving this because",
    "manage your preferences", "update your preferences",
]
_NEWSLETTER_PATTERNS = [r"issue\s*#?\s*\d+", r"\bedition\b", r"weekly\s+digest"]

# Phrases typical of someone selling TO us (outbound vendor spam).
_OUTBOUND_SPAM_PHRASES = [
    "we've helped", "we have helped", "free audit", "quick 15 min call",
    "quick 15-min call", "3x your", "boost your", "grow your organic",
    "isn't ranking", "not ranking", "page 1 of google", "increase your traffic",
    "book a call", "special offer", "limited time offer", "guaranteed results",
    "i noticed your website", "improve your seo", "generate more leads",
]

_INVOICE_PATTERNS = [
    r"\binvoice\b", r"inv[-\s]?\d", r"\bpo[-\s]?\d", r"purchase\s*order",
    r"payment\s*(?:terms|reminder|overdue|due)", r"net\s*\d{1,3}\b",
    r"\bgstin\b", r"\bgst\b.*(?:refund|invoice|billing)", r"overdue",
]


def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _any_sub(subs: list[str], text: str) -> bool:
    low = text.lower()
    return any(s in low for s in subs)


# Word-boundary match for PSU names so short abbreviations ("hal", "bel", "sail")
# don't match inside ordinary words ("Halcyon", "label", "email").
_PSU_NAME_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in _PSU_NAMES) + r")\b", re.IGNORECASE
)


def is_psu(text: str, from_email: str = "") -> bool:
    blob = f"{text}\n{from_email}"
    if _PSU_NAME_RE.search(blob):
        return True
    return _any(_PSU_PATTERNS, blob)


def is_auto_reply(subject: str, text: str) -> bool:
    blob = f"{subject}\n{text}"
    return _any_sub(_AUTOREPLY_PHRASES, blob)


def is_newsletter(subject: str, text: str) -> bool:
    blob = f"{subject}\n{text}"
    if _any_sub(_NEWSLETTER_PHRASES, blob):
        return True
    return _any(_NEWSLETTER_PATTERNS, blob)


def looks_outbound_spam(text: str) -> bool:
    """Heuristic hint for 'they are selling to us'. The LLM makes the final call
    on direction_of_intent; this just flags obvious cases."""
    return _any_sub(_OUTBOUND_SPAM_PHRASES, text)


def is_invoice(text: str) -> bool:
    return _any(_INVOICE_PATTERNS, text)


def detect_all(subject: str, cleaned_body: str, from_email: str = "") -> dict:
    """Bundle every Stage-3 signal for the prompt + rules engine."""
    return {
        "psu": is_psu(cleaned_body, from_email),
        "auto_reply": is_auto_reply(subject, cleaned_body),
        "newsletter": is_newsletter(subject, cleaned_body),
        "outbound_spam": looks_outbound_spam(cleaned_body),
        "invoice": is_invoice(cleaned_body),
    }
