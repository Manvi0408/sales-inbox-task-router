"""Provider-agnostic LLM layer. Uses Groq (OpenAI-compatible) if a key is set,
otherwise Gemini, otherwise nothing (callers fall back to the rules engine).

One place decides the provider, so classifier and chat stay identical."""
from __future__ import annotations

import json
import random
import re
import time

from .config import settings

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_groq_client = None


def provider() -> str | None:
    if settings.groq_api_key:
        return "groq"
    if settings.gemini_api_key:
        return "gemini"
    return None


def available() -> bool:
    return provider() is not None


def active_model() -> str:
    return settings.groq_model if provider() == "groq" else settings.gemini_model


def _groq():
    global _groq_client
    if _groq_client is None:
        from openai import OpenAI

        _groq_client = OpenAI(
            api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1"
        )
    return _groq_client


def _gemini_model(system: str):
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(settings.gemini_model, system_instruction=system)


def _with_retry(fn):
    last: Exception | None = None
    for attempt in range(settings.gemini_max_retries):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - retry any transient error
            last = exc
            if attempt < settings.gemini_max_retries - 1:
                time.sleep((2 ** attempt) + random.uniform(0, 0.5))
    raise last if last else RuntimeError("llm call failed")


def generate(system: str, user: str, *, json_mode: bool = False) -> tuple[str, int]:
    """Return (text, token_count). Raises if the provider call fails after retries."""
    p = provider()
    if p == "groq":
        def call():
            kwargs = {
                "model": settings.groq_model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            r = _groq().chat.completions.create(**kwargs)
            text = r.choices[0].message.content or ""
            tok = int(getattr(getattr(r, "usage", None), "total_tokens", 0) or 0)
            return text, tok
        return _with_retry(call)

    if p == "gemini":
        def call():
            m = _gemini_model(system)
            cfg = {"temperature": 0.0}
            if json_mode:
                cfg["response_mime_type"] = "application/json"
            r = m.generate_content(user, generation_config=cfg)
            text = r.text or ""
            usage = getattr(r, "usage_metadata", None)
            tok = int(getattr(usage, "total_token_count", 0) or 0) if usage else 0
            return text, tok
        return _with_retry(call)

    raise RuntimeError("no LLM provider configured")


def parse_json(text: str) -> dict:
    m = _JSON_RE.search(text or "")
    if not m:
        raise ValueError("no JSON object in model output")
    return json.loads(m.group(0))
