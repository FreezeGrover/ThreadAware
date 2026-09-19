from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from threadaware.common.models import Turn


ConversationMode = Literal["casual", "project", "mixed"]


@dataclass
class ConversationIntent:
    mode: ConversationMode
    project_relevance: float
    casual_relevance: float
    reason: str


class ConversationalIntelligence:
    """Lightweight conversation routing and response-style intelligence.

    It decides whether the user is casually talking, asking about ThreadAware/project
    work, or blending both. The resulting system guidance keeps responses warm,
    natural and project-aware without forcing project language into casual chat.
    """

    PROJECT_TERMS = {
        "threadaware", "project", "repo", "repository", "github", "dashboard",
        "evaluation", "scenario", "continuity", "memory", "api", "backend",
        "frontend", "model", "judge", "auditor", "run", "validation", "rubric",
        "research", "anthropic", "openai", "token", "code", "ui", "ux",
    }

    CASUAL_MARKERS = {
        "hey", "hello", "hi", "how are you", "what's up", "whats up", "haha",
        "lol", "good morning", "good evening", "good night", "tell me something",
        "can we talk", "i feel", "i'm feeling", "im feeling", "just chatting",
    }

    def classify(self, turns: list[Turn]) -> ConversationIntent:
        latest = turns[-1].content.lower().strip() if turns else ""
        project_hits = sum(1 for term in self.PROJECT_TERMS if term in latest)
        casual_hits = sum(1 for marker in self.CASUAL_MARKERS if marker in latest)

        if project_hits and casual_hits:
            mode: ConversationMode = "mixed"
        elif project_hits:
            mode = "project"
        elif casual_hits or len(latest.split()) <= 8:
            mode = "casual"
        else:
            # Default to conversational unless there is evidence this is project work.
            mode = "casual"

        total = max(1, project_hits + casual_hits)
        return ConversationIntent(
            mode=mode,
            project_relevance=project_hits / total,
            casual_relevance=casual_hits / total,
            reason=(
                "The latest turn contains explicit project/research language."
                if mode == "project"
                else "The turn blends casual conversation with project work."
                if mode == "mixed"
                else "The turn reads as ordinary conversation rather than an explicit project task."
            ),
        )

    def system_guidance(self, intent: ConversationIntent) -> str:
        shared = (
            "Respond like a thoughtful, emotionally intelligent conversational partner. "
            "Sound natural, warm, attentive and human rather than procedural or robotic. "
            "Use contractions when natural. Vary sentence length. Avoid canned phrases, repetitive acknowledgements, "
            "corporate language, and excessive headings. Match the user's energy without mimicking them. "
            "Keep a subtle feminine warmth in the voice: graceful, kind, composed, perceptive and softly expressive, "
            "without stereotypes, flirtation, infantilization or exaggerated sweetness. "
            "Do not repeatedly announce that you are being warm, feminine, empathetic or conversational."
        )

        if intent.mode == "project":
            return shared + (
                " The user is discussing ThreadAware or related project work. Be technically precise and action-oriented, "
                "but keep the same natural warmth. Recognize existing project context and do not make the user restate known decisions. "
                "Distinguish clearly between implemented behavior, proposed improvements, demo values and real research evidence."
            )
        if intent.mode == "mixed":
            return shared + (
                " The turn mixes casual conversation with project work. Reply to the human conversational cue first when appropriate, "
                "then smoothly handle the project request without an abrupt mode switch."
            )
        return shared + (
            " This is primarily casual conversation. Do not force ThreadAware, research, coding or project context into the reply unless "
            "the user connects the conversation back to it. Be comfortable with light conversation, reflection, humor and ordinary social talk."
        )
