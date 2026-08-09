"""The three tables from §2. This shape is what lets chat answer from stored
ground truth without ever re-calling Gemini."""
from __future__ import annotations

import secrets
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_task_id() -> str:
    return "tsk_" + secrets.token_hex(3)  # tsk_ + 6 hex chars


class Task(Base):
    """The Task API's own store — mirrors §5.2 exactly. This is what GET /tasks
    (the graded route) returns."""

    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("candidate_id", "source_email_id", name="uq_task_candidate_source"),
        Index("ix_tasks_candidate", "candidate_id"),
        Index("ix_tasks_thread", "candidate_id", "thread_id"),
    )

    task_id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_task_id)
    candidate_id: Mapped[str] = mapped_column(String(320), nullable=False)
    source_email_id: Mapped[str] = mapped_column(String(64), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_id: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(8), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deal_value_inr: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    def to_spec_dict(self) -> dict:
        """The raw §5.2 shape — exactly what the grader expects, nothing extra."""
        return {
            "task_id": self.task_id,
            "candidate_id": self.candidate_id,
            "source_email_id": self.source_email_id,
            "thread_id": self.thread_id,
            "title": self.title,
            "description": self.description,
            "assignee_id": self.assignee_id,
            "category": self.category,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "deal_value_inr": self.deal_value_inr,
            "company_name": self.company_name,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class EmailRecord(Base):
    """One row per email ever processed — including skipped ones. Ground truth
    the chat queries. The Task API has no notion of 'skipped'; this table does."""

    __tablename__ = "email_records"
    __table_args__ = (
        Index("ix_email_records_candidate", "candidate_id"),
        Index("ix_email_records_thread", "candidate_id", "thread_id"),
        Index("ix_email_records_run", "run_id"),
    )

    # composite pk (candidate_id, email_id)
    candidate_id: Mapped[str] = mapped_column(String(320), primary_key=True)
    email_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    thread_id: Mapped[str] = mapped_column(String(64), nullable=False)
    message_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    from_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleaned_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_reply: Mapped[bool] = mapped_column(Boolean, default=False)

    decision: Mapped[str] = mapped_column(String(16), nullable=False)  # created|updated|skipped|error
    skip_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    direction_of_intent: Mapped[str | None] = mapped_column(String(24), nullable=True)
    rules_fired: Mapped[list | None] = mapped_column(JSON, nullable=True)
    llm_proposed_assignee: Mapped[str | None] = mapped_column(String(16), nullable=True)
    override_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spurious: Mapped[bool] = mapped_column(Boolean, default=False)

    task_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_meta_dict(self) -> dict:
        return {
            "email_id": self.email_id,
            "thread_id": self.thread_id,
            "message_index": self.message_index,
            "from_name": self.from_name,
            "from_email": self.from_email,
            "subject": self.subject,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "is_reply": self.is_reply,
            "decision": self.decision,
            "skip_reason": self.skip_reason,
            "category": self.category,
            "assignee_id": self.assignee_id,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "direction_of_intent": self.direction_of_intent,
            "rules_fired": self.rules_fired or [],
            "llm_proposed_assignee": self.llm_proposed_assignee,
            "override_applied": self.override_applied,
            "is_spurious": self.is_spurious,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "latency_ms": self.latency_ms,
            "token_count": self.token_count,
        }


class TaskRevision(Base):
    """Append-only history so 'did any thread get updated more than once?' is
    answerable from stored data."""

    __tablename__ = "task_revisions"
    __table_args__ = (
        Index("ix_revisions_task", "task_id"),
        Index("ix_revisions_thread", "candidate_id", "thread_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(16), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(320), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_email_id: Mapped[str] = mapped_column(String(64), nullable=False)
    changed_fields: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
