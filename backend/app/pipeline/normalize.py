"""Stage 1 — normalise. Strip HTML to text and cut quoted reply chains /
forwarded blocks so we never classify or re-extract values from quoted text."""
from __future__ import annotations

import re
from html import unescape

_TAG_RE = re.compile(r"<[^>]+>")
_STYLE_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"[ \t]+")
_MULTINEWLINE_RE = re.compile(r"\n{3,}")

# Lines that mark the start of a quoted / forwarded block. Everything from the
# first such marker onward is dropped.
_QUOTE_MARKERS = [
    re.compile(r"^\s*On .*wrote:\s*$", re.IGNORECASE),
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}", re.IGNORECASE),
    re.compile(r"^\s*-{2,}\s*Forwarded message\s*-{2,}", re.IGNORECASE),
    re.compile(r"^\s*_{5,}\s*$"),
    re.compile(r"^\s*From:\s.*$", re.IGNORECASE),
    re.compile(r"^\s*Sent:\s.*$", re.IGNORECASE),
    re.compile(r"^\s*>{1,}"),  # quoted line prefix
]


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = _STYLE_SCRIPT_RE.sub(" ", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub(" ", text)
    text = unescape(text)
    return text


def strip_quoted(text: str) -> str:
    """Cut at the first quoted/forwarded marker. Keeps only the new message."""
    lines = text.splitlines()
    kept: list[str] = []
    for line in lines:
        if any(m.search(line) for m in _QUOTE_MARKERS):
            break
        kept.append(line)
    cleaned = "\n".join(kept)
    # If cutting removed everything (e.g. body was entirely a quote), fall back
    # to the pre-cut text so we don't lose a genuinely short message.
    return cleaned if cleaned.strip() else text


def clean_body(raw: str) -> str:
    """Full Stage-1 pipeline: HTML -> text -> drop quoted chain -> tidy space."""
    if not raw:
        return ""
    text = strip_html(raw)
    text = strip_quoted(text)
    text = _WS_RE.sub(" ", text)
    text = _MULTINEWLINE_RE.sub("\n\n", text)
    return text.strip()
