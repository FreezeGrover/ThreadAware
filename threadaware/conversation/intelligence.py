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

    def demo_reply(self, turns: list[Turn], intent: ConversationIntent | None = None) -> str:
        """Return a useful, warm offline reply without pretending a model was called.

        Demo mode remains deterministic and deliberately modest. It lets reviewers
        exercise the conversational UI and continuity pipeline before a server-side
        API key is configured, while live mode keeps the full model-backed behavior.
        """
        latest = turns[-1].content.strip() if turns else ""
        lower = latest.lower()
        intent = intent or self.classify(turns)

        if any(marker in lower for marker in ("hello", "hey", "hi ", "good morning", "good evening")):
            return "Hi — it’s genuinely nice to meet you. What would you like to think through together?"

        if any(word in lower for word in ("stress", "overwhelmed", "anxious", "wellbeing", "well-being", "sleep")):
            return (
                "I’m sorry this is feeling heavy. We can slow it down and take one piece at a time. "
                "What feels most difficult right now—and has anything important changed since it began?"
            )

        if any(word in lower for word in ("pain", "symptom", "doctor", "health", "medicine")):
            return (
                "I can help you organize what you’re noticing and think through sensible next steps. "
                "What symptoms are you having, when did they start, and is anything getting rapidly worse?"
            )

        if intent.mode in {"project", "mixed"}:
            return (
                "Absolutely—I’m with you. Tell me the outcome you want and the constraint that matters most; "
                "I’ll keep the earlier context connected as the project evolves."
            )

        if latest.endswith("?"):
            return (
                "Let’s work it through carefully. What detail would most change the answer for you, "
                "or what have you already tried?"
            )

        return (
            "I’m following. Tell me a little more about what matters most here, and I’ll keep track "
            "as the conversation develops."
        )
