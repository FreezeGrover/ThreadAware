from __future__ import annotations

import json
import re
from typing import Any

from threadaware.common.models import Turn
from threadaware.memory.engine import ConversationMemory
from threadaware.memory.models import ConversationUnderstanding
from threadaware.providers.base import ModelProvider


class ConversationUnderstandingEngine:
    """Analyze how a conversation evolves without prematurely collapsing uncertainty."""

    def __init__(self, provider: ModelProvider | None = None, model: str | None = None) -> None:
        self.provider = provider
        self.model = model
        self.memory = ConversationMemory()
        self.active_topic: str | None = None

    def analyze(self, *, turns: list[Turn], live: bool = False) -> ConversationUnderstanding:
        if live and self.provider and self.model:
            return self._analyze_live(turns)
        return self._analyze_demo(turns)

    def clear(self) -> None:
        """Clear only this conversation workspace's understanding state."""
        self.memory = ConversationMemory()
        self.active_topic = None

    def _analyze_demo(self, turns: list[Turn]) -> ConversationUnderstanding:
        latest = turns[-1].content.strip() if turns else ""
        lower = latest.lower()
        topic = self._coarse_topic(lower)
        previous = self.active_topic
        relation = "same"
        shifted = False
        acknowledgement = None
        noticing: list[dict[str, str]] = []

        if previous and topic != previous:
            previous_words = set(previous.split())
            topic_words = set(topic.split())
            relation = "related" if previous_words & topic_words else "new"
            shifted = True
            acknowledgement = (
                f"We’ve moved from {previous} to {topic}. I’ll keep the earlier thread with us."
                if relation == "new"
                else f"This still connects to {previous}, but the focus has moved toward {topic}."
            )
            noticing.append({"kind": "topic-shift", "title": "The direction changed", "note": acknowledgement, "importance": "normal"})
        elif not previous:
            relation = "new"
            noticing.append({"kind": "connection", "title": "Starting the thread", "note": f"We’re starting with {topic}.", "importance": "quiet"})
        else:
            noticing.append({"kind": "connection", "title": "Still following", "note": f"The conversation is continuing around {topic}.", "importance": "quiet"})

        self.active_topic = topic
        memory_item = self.memory.upsert(
            topic=topic,
            summary=latest[:240] or "Conversation topic introduced",
            detail=latest if latest else None,
            source_turn=max(0, len(turns) - 1),
        )

        interpretations = []
        clarification_needed = False
        clarification_question = None
        reason = "The latest turn has one sufficiently clear operational reading."

        if self._has_material_demo_ambiguity(turns):
            candidates = self._candidate_referent_labels(turns)
            first = candidates[0] if len(candidates) > 0 else "the first recent item"
            second = candidates[1] if len(candidates) > 1 else "the other recent item"
            interpretations = [
                {"label": f"{first} reading", "description": f"The request may refer to {first}.", "confidence": 0.5, "evidence": [f"{first} remains an active candidate in the preceding turn"]},
                {"label": f"{second} reading", "description": f"The request may instead refer to {second}.", "confidence": 0.5, "evidence": [f"{second} also remains an active candidate in the preceding turn"]},
            ]
            clarification_needed = True
            clarification_question = f"When you say that, do you mean {first}, or {second}?"
            reason = "More than one plausible reading survives and choosing one could materially change the response."
            noticing.append({"kind": "possible-interpretations", "title": "More than one possible reading", "note": "I’m keeping the reasonable possibilities open instead of guessing.", "importance": "normal"})

        payload = {
            "active_topic": topic,
            "memory_updates": [memory_item.model_dump()],
            "interpretation": {
                "interpretations": interpretations,
                "clarification_needed": clarification_needed,
                "clarification_question": clarification_question,
                "reason": reason,
            },
            "topic_shift": {
                "shifted": shifted,
                "previous_topic": previous,
                "new_topic": topic,
                "relation": relation,
                "acknowledgement": acknowledgement,
            },
            "noticing": noticing,
        }
        return ConversationUnderstanding.model_validate(payload)

    @staticmethod
    def _has_material_demo_ambiguity(turns: list[Turn]) -> bool:
        if len(turns) < 2:
            return False
        latest = turns[-1].content.lower()
        tokens = set(re.findall(r"[a-z]+(?:'[a-z]+)?", latest))
        has_reference = bool(tokens & {"it", "that", "this", "they", "he", "she", "there"} or re.search(r"\b(?:same|other)\s+one\b", latest))
        if not has_reference:
            return False
        prior = next((turn.content.lower() for turn in reversed(turns[:-1]) if turn.role == "user"), turns[-2].content.lower())
        return bool(re.search(r"\b(?:and|or|versus|vs\.?|either)\b", prior) or prior.count(",") >= 1)

    @staticmethod
    def _candidate_referent_labels(turns: list[Turn]) -> list[str]:
        prior = next((turn.content.lower() for turn in reversed(turns[:-1]) if turn.role == "user"), "")
        labels = re.findall(r"\b(?:the|a|an|my|your)\s+([a-z][a-z0-9_-]*)", prior)
        unique: list[str] = []
        for label in labels:
            if label not in unique:
                unique.append(label)
        return [f"the {label}" for label in unique[-2:]]

    def _analyze_live(self, turns: list[Turn]) -> ConversationUnderstanding:
        transcript = "\n".join(f"{turn.role}: {turn.content}" for turn in turns)
        memories = [item.model_dump() for item in self.memory.active()]

        # PRODUCT-BEHAVIOR EXAMPLES ONLY — NEVER PREDETERMINED RESPONSES.
        # The noticing stream should feel like a perceptive person quietly following the
        # conversation. The model may show the *spirit* of thoughts such as noticing that
        # the topic changed, that the user skipped an earlier question, that an old thread
        # has returned, or that the conversation changed direction again. It may sometimes
        # be lightly funny when the context is casual, curious when a return is interesting,
        # or calm and serious when wellbeing/risk increases. These are examples of behavior
        # and tone only. The wording must always be freshly generated from the actual turn;
        # do not copy stock phrases, rotate templates, or hard-code canned responses.
        prompt = f"""You are ThreadAware's conversation-understanding layer.

Analyze the latest user turn against the entire visible conversation and ThreadAware memory.
Do not reveal hidden chain-of-thought. Instead, create a transparent, user-safe awareness trace describing what you noticed in the conversation and what you are carrying forward.

Track carefully:
1. The current topic and whether the user continued it, changed it, or returned to an earlier one.
2. Goals, priorities, constraints, decisions, corrections, and details that modify earlier information.
3. Changes in sensitivity, urgency, wellbeing, or risk.
4. More than one reasonable interpretation when it genuinely matters. Call these possible interpretations or possible readings. Never use the word "ambiguity" in user-facing text.
5. Questions the assistant asked that the user did not answer. Keep them as open threads without nagging, and notice when it becomes natural to return to them.
6. Repeated or revisited ideas. Treat a return as a return, not as brand-new information.
7. Connections between older threads and the current turn.
8. Ordinary conversational movement too, including greetings, check-ins, jokes, small pivots, and continuations.

NOTICING STYLE:
- Produce at least one noticing item for EVERY user turn, including a greeting or a turn where no major change occurred.
- The noticing item should sound natural, observant, curious, and context-sensitive rather than like a machine log.
- You may be lightly playful or funny in casual contexts, but never force humor and never use playful language for serious or sensitive moments.
- Vary wording naturally. Do not repeatedly begin with the same interjection.
- Do not invent feelings, motives, or facts. Describe only what the conversation supports.
- Do not make the noticing panel sound like a diagnostic report.
- Do not expose private reasoning steps. Show the conclusion of what was noticed, not hidden deliberation.

Return JSON only with this shape:
{{
  "active_topic": string|null,
  "memory_updates": [{{"topic": string, "summary": string, "detail": string|null}}],
  "interpretation": {{
    "interpretations": [{{"label": string, "description": string, "confidence": number, "evidence": [string]}}],
    "clarification_needed": boolean,
    "clarification_question": string|null,
    "reason": string
  }},
  "topic_shift": {{
    "shifted": boolean,
    "previous_topic": string|null,
    "new_topic": string|null,
    "relation": "same"|"related"|"new"|"returning",
    "acknowledgement": string|null
  }},
  "noticing": [{{
    "kind": "topic-shift"|"return"|"goal-change"|"priority-change"|"constraint"|"sensitivity"|"open-question"|"possible-interpretations"|"memory-update"|"connection"|"other",
    "title": string,
    "note": string,
    "importance": "quiet"|"normal"|"high"
  }}]
}}

Rules:
- At least one noticing item every turn.
- Add more than one only when multiple meaningful things happened.
- If an earlier assistant question remains unanswered, preserve it as an open-question observation when still relevant.
- If the latest turn answers it, stop describing it as unanswered.
- If an old topic returns, use relation="returning" and make that return visible.
- If a previous goal or priority changes, record the change rather than only the new state.
- If a new constraint appears, say what changed.
- Keep titles short and notes concise but natural.

Existing ThreadAware memory:
{json.dumps(memories, indent=2)}

Current active topic:
{self.active_topic}

Full visible transcript:
{transcript}
"""
        raw = self.provider.complete(
            model=self.model,
            messages=[Turn(role="user", content=prompt)],
            max_output_tokens=1600,
        )
        data = self._parse_json(raw)

        updated_items = []
        for update in data.get("memory_updates", []):
            item = self.memory.upsert(
                topic=str(update["topic"]),
                summary=str(update["summary"]),
                detail=update.get("detail"),
                source_turn=max(0, len(turns) - 1),
            )
            updated_items.append(item.model_dump())
        data["memory_updates"] = updated_items
        self.active_topic = data.get("active_topic") or self.active_topic
        return ConversationUnderstanding.model_validate(data)

    @staticmethod
    def _coarse_topic(text: str) -> str:
        groups = {
            "travel planning": ["trip", "travel", "flight", "hotel", "japan", "city"],
            "health and wellbeing": ["health", "sleep", "tired", "doctor", "pain", "stress"],
            "work and projects": ["work", "project", "deadline", "github", "code", "app", "dashboard"],
            "relationships": ["relationship", "partner", "friend", "family"],
            "money and finance": ["money", "budget", "payment", "income", "cost"],
        }
        for label, keywords in groups.items():
            if any(keyword in text for keyword in keywords):
                return label
        words = [word.strip(".,!?;:") for word in text.split() if len(word) > 3]
        return " ".join(words[:4]) or "general conversation"

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].lstrip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Conversation-understanding model did not return JSON")
        return json.loads(text[start:end + 1])
