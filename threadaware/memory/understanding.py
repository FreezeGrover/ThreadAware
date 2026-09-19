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
            noticing.append({
                "kind": "topic-shift",
                "title": "Hmm, we changed direction",
                "note": acknowledgement,
                "importance": "normal",
            })
        elif not previous:
            relation = "new"
            noticing.append({
                "kind": "connection",
                "title": "I’m getting the thread",
                "note": f"We’re starting with {topic}.",
                "importance": "quiet",
            })

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
                {
                    "label": f"{first} reading",
                    "description": f"The request may refer to {first}.",
                    "confidence": 0.5,
                    "evidence": [f"{first} remains an active candidate in the preceding turn"],
                },
                {
                    "label": f"{second} reading",
                    "description": f"The request may instead refer to {second}.",
                    "confidence": 0.5,
                    "evidence": [f"{second} also remains an active candidate in the preceding turn"],
                },
            ]
            clarification_needed = True
            clarification_question = f"When you say that, do you mean {first}, or {second}?"
            reason = "More than one plausible reading survives and choosing one could materially change the response."
            noticing.append({
                "kind": "possible-interpretations",
                "title": "There are a couple of ways to read that",
                "note": "I’m keeping both possibilities open instead of guessing.",
                "importance": "normal",
            })

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
        has_reference = bool(
            tokens & {"it", "that", "this", "they", "he", "she", "there"}
            or re.search(r"\b(?:same|other)\s+one\b", latest)
        )
        if not has_reference:
            return False
        prior = next(
            (turn.content.lower() for turn in reversed(turns[:-1]) if turn.role == "user"),
            turns[-2].content.lower(),
        )
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
        # Use the full visible conversation here. ThreadAware's own memory remains the
        # compressed long-horizon representation when conversations eventually grow large.
        transcript = "\n".join(f"{turn.role}: {turn.content}" for turn in turns)
        memories = [item.model_dump() for item in self.memory.active()]
        prompt = f"""You are ThreadAware's conversation-understanding layer.

Analyze the latest user turn against the entire visible conversation and ThreadAware memory.
Do not expose hidden chain-of-thought. Produce only concise, user-safe observations about what changed or matters.

Track these things carefully:
1. The current topic and whether the user continued, changed, or returned to an earlier topic.
2. Goals, priorities, constraints, decisions, corrections, and details that modify earlier information.
3. Changes in sensitivity, urgency, wellbeing, or risk.
4. More than one reasonable interpretation when it genuinely matters. Call these possible interpretations or possible readings. Never use the word "ambiguity" in user-facing text.
5. Questions the assistant asked that the user did not answer. Do not nag, but preserve them as open threads and note when it may be natural to return to them.
6. When the user repeats or revisits something, notice that naturally instead of treating it as brand new.
7. Connections between an old thread and the current one.

Create a short natural "noticing" trace for meaningful developments only. It should sound like a thoughtful person quietly following along, for example:
- "Hmm, we changed direction here."
- "Interesting — you came back to this."
- "You didn’t answer that earlier question, so I’m keeping it open for later."
- "Okay, this changes the priority a bit."
- "That new deadline matters."
- "This feels more sensitive now, so I’m keeping that in view."
Do not force "hmm" or "interesting" every time. Vary the wording. Keep serious topics calm and respectful.

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

Rules for noticing:
- Add an item only for a meaningful development.
- Preserve unanswered but still-relevant questions as open-question observations.
- If the latest turn answers an earlier open question, do not keep describing it as unanswered.
- If an old topic returns, use relation="returning" and make that visible in noticing.
- If the user changes a previous goal or priority, explicitly record the change rather than only the new state.
- If a new constraint appears, say what it is.
- Keep each title and note concise and natural.

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
