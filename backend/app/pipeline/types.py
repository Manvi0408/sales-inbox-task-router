"""Shared classification object produced by the LLM (or the rules fallback) and
mutated by the rules engine before it becomes a task."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Classification:
    is_actionable: bool = True
    skip_reason: str | None = None
    category: str = "triage"
    assignee_id: str = "u_triage"
    priority: str = "medium"
    due_date: date | None = None
    deal_value_inr: int | None = None
    company_name: str | None = None
    confidence: float = 0.5
    reasoning: str = ""
    direction_of_intent: str = "inbound_buyer"
    title: str = ""
    description: str = ""

    # provenance
    llm_proposed_assignee: str | None = None
    rules_fired: list[str] = field(default_factory=list)
    override_applied: bool = False
    source: str = "llm"  # "llm" | "fallback"
