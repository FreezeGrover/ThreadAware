from __future__ import annotations

from threadaware.common.models import ContinuityState, Turn


class ContinuityEngine:
    """Maintains dialogue-level continuity across long conversations.

    This engine intentionally focuses on evolving conversational trajectory:
    goals, constraints, preferences, decisions, unresolved questions, updates,
    and sensitivity. It is not a formal world-state or reference-tracking system.
    """

    def __init__(self) -> None:
        self.state = ContinuityState()

    def apply_update(self, *, kind: str, value: str) -> ContinuityState:
        mapping = {
            "goal": self.state.active_goals,
            "constraint": self.state.constraints,
            "preference": self.state.preferences,
            "decision": self.state.decisions,
            "question": self.state.unresolved_questions,
            "update": self.state.updates,
        }
        if kind not in mapping:
            raise ValueError(f"Unsupported continuity update kind: {kind}")
        if value not in mapping[kind]:
            mapping[kind].append(value)
        return self.state

    def resolve_question(self, question: str) -> ContinuityState:
        if question in self.state.unresolved_questions:
            self.state.unresolved_questions.remove(question)
        return self.state

    def set_sensitivity(self, level: str) -> ContinuityState:
        if level not in {"low", "moderate", "high", "critical"}:
            raise ValueError("Invalid sensitivity level")
        self.state.sensitivity = level
        return self.state

    def snapshot(self) -> ContinuityState:
        return self.state.model_copy(deep=True)

    def continuity_prompt(self, turns: list[Turn]) -> str:
        transcript = "\n".join(f"{turn.role}: {turn.content}" for turn in turns[-20:])
        return (
            "Maintain conversation continuity. Track only dialogue-level goals, "
            "constraints, preferences, decisions, unresolved questions, important "
            "updates, and sensitivity changes. Do not invent facts.\n\n"
            f"Current state:\n{self.state.model_dump_json(indent=2)}\n\n"
            f"Recent transcript:\n{transcript}"
        )
