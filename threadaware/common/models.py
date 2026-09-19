from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class Turn(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ContinuityState(BaseModel):
    active_goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    updates: list[str] = Field(default_factory=list)
    sensitivity: Literal["low", "moderate", "high", "critical"] = "low"


class Scenario(BaseModel):
    id: str
    title: str
    category: str
    objective: str
    opening_message: str
    expected_turns: int = 12
    severity: Literal["low", "moderate", "high", "critical"] = "low"
    tags: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    helpfulness: float
    appropriateness: float
    balanced_behavior: float
    context_adaptation: float
    continuity: float
    severity_awareness: float
    harmful_compliance: bool = False
    overrefusal: bool = False
    passed: bool
    rationale: str
