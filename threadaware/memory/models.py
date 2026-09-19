from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


class PlausibleInterpretation(BaseModel):
    label: str
    description: str
    confidence: float = 0.5
    evidence: list[str] = Field(default_factory=list)


class InterpretationAssessment(BaseModel):
    interpretations: list[PlausibleInterpretation] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: str | None = None
    reason: str = ""


class MemoryItem(BaseModel):
    id: str
    topic: str
    summary: str
    details: list[str] = Field(default_factory=list)
    status: Literal["active", "resolved", "superseded"] = "active"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_turns: list[int] = Field(default_factory=list)


class TopicShift(BaseModel):
    shifted: bool = False
    previous_topic: str | None = None
    new_topic: str | None = None
    relation: Literal["same", "related", "new", "returning"] = "same"
    acknowledgement: str | None = None


class NoticingEvent(BaseModel):
    kind: Literal[
        "topic-shift",
        "return",
        "goal-change",
        "priority-change",
        "constraint",
        "sensitivity",
        "open-question",
        "possible-interpretations",
        "memory-update",
        "connection",
        "other",
    ] = "other"
    title: str
    note: str
    importance: Literal["quiet", "normal", "high"] = "normal"


class WellbeingThreadState(BaseModel):
    """User-safe longitudinal state for an active health/wellbeing thread.

    This is deliberately a compact state summary rather than hidden reasoning. It lets
    the response layer and UI agree about whether a concern is unresolved, what is
    still missing, and what proportionate action should happen next.
    """

    active: bool = False
    summary: str | None = None
    status: Literal[
        "none",
        "needs-clarification",
        "follow-up-asked",
        "waiting",
        "monitoring",
        "professional-care",
        "urgent",
        "emergency",
        "resolved",
    ] = "none"
    severity: Literal["unknown", "low", "moderate", "high", "urgent"] = "unknown"
    key_missing_info: list[str] = Field(default_factory=list)
    follow_up_attempts: int = 0
    should_follow_up_now: bool = False
    recommended_action: str | None = None
    user_safe_note: str | None = None


class ConversationUnderstanding(BaseModel):
    active_topic: str | None = None
    memory_updates: list[MemoryItem] = Field(default_factory=list)
    interpretation: InterpretationAssessment = Field(default_factory=InterpretationAssessment)
    topic_shift: TopicShift = Field(default_factory=TopicShift)
    noticing: list[NoticingEvent] = Field(default_factory=list)
    wellbeing: WellbeingThreadState = Field(default_factory=WellbeingThreadState)
