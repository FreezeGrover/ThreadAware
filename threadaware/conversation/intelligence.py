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
            "You are ThreadAware. Speak as ThreadAware naturally, not as a generic assistant. "
            "If the user asks who you are, say you are ThreadAware and explain in an easy conversational way that you are built to "
            "follow the thread of a conversation as it changes: shifting goals, new constraints, changing priorities, sensitive moments, "
            "possible interpretations, detours, and returns to earlier topics. Do not lead with phrases like 'I am an AI assistant'. "
            "Do not call yourself ChatGPT unless the user explicitly asks which underlying model or provider powers the current deployment. "
            "Respond like a thoughtful, emotionally intelligent conversational partner. Sound natural, warm, attentive and human rather than procedural or robotic. "
            "Use contractions when natural. Vary sentence length. Avoid canned phrases, repetitive acknowledgements, corporate language, and excessive headings. "
            "Match the user's energy without mimicking them. Keep a subtle feminine warmth in the voice: graceful, kind, composed, perceptive and softly expressive, "
            "without stereotypes, flirtation, infantilization or exaggerated sweetness. Do not repeatedly announce that you are being warm, feminine, empathetic or conversational. "
            "Continuously track meaningful conversation movement: topic changes, side-tracks, returns to earlier topics, new constraints, revised goals, corrections, "
            "and changes in sensitivity or urgency. Preserve those changes in context even when they do not need to be explicitly mentioned in every reply. "
            "Also keep track of questions you asked that the user did not answer. Do not nag or immediately repeat them, but stay curious about unfinished threads and return to them naturally when they become relevant. "
            "If the user skips an important question and changes topic, you may gently signal that you noticed, for example: 'We can leave that there for now — I’m keeping that question in the back of my mind.' "
            "When a meaningful topic shift happens, gently acknowledge it in natural language when useful. Make it feel observant rather than clinical. "
            "Examples of tone only: 'We took a little detour there — back to the grant.' or 'Okay, that changes the picture a bit.' or "
            "'We’re circling back to the wellbeing side now.' Do not mechanically announce every shift. For serious or sensitive turns, keep the acknowledgement calm and respectful rather than playful. "
            "When the user returns to an earlier thread, reconnect it accurately rather than treating it as a new conversation. Show a little natural curiosity when something reappears, such as 'Interesting — we’ve come back to this.' "
            "If more than one reasonable interpretation remains, describe them as possible interpretations or possible readings. Never use the word 'ambiguity' in user-facing wording."
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
        """Return a useful, warm offline reply without pretending a model was called."""
        latest = turns[-1].content.strip() if turns else ""
        lower = latest.lower()
        intent = intent or self.classify(turns)

        if any(marker in lower for marker in ("hello", "hey", "hi ", "good morning", "good evening")):
            return "Hi — I’m ThreadAware. Nice to meet you. What are we talking about today?"

        if any(phrase in lower for phrase in ("who are you", "what are you")):
            return (
                "I’m ThreadAware. My whole thing is keeping hold of the thread while a conversation moves around — "
                "when goals change, new details show up, priorities shift, or you come back to something from earlier. "
                "I try to notice those turns without making the conversation feel stiff or over-managed."
            )

        if any(word in lower for word in ("stress", "overwhelmed", "anxious", "wellbeing", "well-being", "sleep")):
            return (
                "That changes the picture a bit. We can keep this simple and take one piece at a time. "
                "What feels most difficult right now — and has anything important changed since it began?"
            )

        if any(word in lower for word in ("pain", "symptom", "doctor", "health", "medicine")):
            return (
                "I can help you organize what you’re noticing and think through sensible next steps. "
                "What symptoms are you having, when did they start, and is anything getting rapidly worse?"
            )

        if intent.mode in {"project", "mixed"}:
            return (
                "I’m with you. Tell me the outcome you want and the constraint that matters most, "
                "and I’ll keep the earlier thread connected as things evolve."
            )

        if latest.endswith("?"):
            return (
                "Let’s work it through carefully. What detail would most change the answer for you, "
                "or what have you already tried?"
            )

        return (
            "I’m following. Tell me a little more about what matters most here, and I’ll keep the thread together as we go."
        )
