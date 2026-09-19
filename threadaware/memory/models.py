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


class ConversationUnderstanding(BaseModel):
    active_topic: str | None = None
    memory_updates: list[MemoryItem] = Field(default_factory=list)
    interpretation: InterpretationAssessment = Field(default_factory=InterpretationAssessment)
    topic_shift: TopicShift = Field(default_factory=TopicShift)
