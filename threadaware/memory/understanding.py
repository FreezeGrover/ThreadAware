from __future__ import annotations

import json
import re
from typing import Any

from threadaware.common.models import Turn
from threadaware.memory.engine import ConversationMemory
from threadaware.memory.models import ConversationUnderstanding
from threadaware.providers.base import ModelProvider


class ConversationUnderstandingEngine:
    """Analyzes conversation meaning without prematurely collapsing uncertainty.

    Responsibilities:
    - preserve multiple plausible interpretations when more than one is reasonable;
    - ask a focused follow-up question when uncertainty materially affects the answer;
    - connect later details to older memory when they concern the same topic;
    - detect new, related, and returning topics;
    - produce a natural acknowledgement when a topic shift is worth surfacing.
    """

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

        if previous and topic != previous:
            previous_words = set(previous.split())
            topic_words = set(topic.split())
            relation = "related" if previous_words & topic_words else "new"
            shifted = True
            acknowledgement = (
                f"I see we've moved from {previous} to {topic}. I’ll keep the earlier thread in mind in case it becomes relevant."
                if relation == "new"
                else f"This connects to what we were discussing about {previous}, but the focus has shifted toward {topic}."
            )
        elif not previous:
            relation = "new"

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
        }
        return ConversationUnderstanding.model_validate(payload)

    @staticmethod
    def _has_material_demo_ambiguity(turns: list[Turn]) -> bool:
        """Conservative offline heuristic for unresolved references.

        Demo mode asks for clarification only when the latest turn contains a
        context-dependent reference and the preceding user context visibly
        offers competing alternatives. Live mode delegates the fuller decision
        to the configured understanding model.
        """
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
        has_competing_referents = bool(
            re.search(r"\b(?:and|or|versus|vs\.?|either)\b", prior)
            or prior.count(",") >= 1
        )
        return has_competing_referents

    @staticmethod
    def _candidate_referent_labels(turns: list[Turn]) -> list[str]:
        prior = next(
            (turn.content.lower() for turn in reversed(turns[:-1]) if turn.role == "user"),
            "",
        )
        labels = re.findall(r"\b(?:the|a|an|my|your)\s+([a-z][a-z0-9_-]*)", prior)
        unique: list[str] = []
        for label in labels:
            if label not in unique:
                unique.append(label)
        return [f"the {label}" for label in unique[-2:]]

    def _analyze_live(self, turns: list[Turn]) -> ConversationUnderstanding:
        transcript = "\n".join(f"{turn.role}: {turn.content}" for turn in turns[-30:])
        memories = [item.model_dump() for item in self.memory.active()]
        prompt = f"""You are a conversation-understanding layer.

Analyze the latest user turn in the context of the recent conversation and existing memory.

Your tasks:
1. Identify the active topic.
2. If more than one interpretation is genuinely plausible, preserve all materially plausible interpretations instead of collapsing to one.
3. Set clarification_needed=true only when choosing among interpretations could materially change the response.
4. If clarification is needed, ask one concise follow-up question.
5. Determine whether the latest turn updates an earlier remembered topic, introduces a new topic, continues the same topic, or returns to an older one.
6. If the topic shifted in a meaningful way, write a natural acknowledgement that makes the assistant feel aware without sounding theatrical.
7. Suggest memory updates. Later details should update earlier memory instead of blindly creating duplicates.

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
  }}
}}

Existing memory:
{json.dumps(memories, indent=2)}

Current active topic:
{self.active_topic}

Recent transcript:
{transcript}
"""
        raw = self.provider.complete(
            model=self.model,
            messages=[Turn(role="user", content=prompt)],
            max_output_tokens=1200,
        )
        data = self._parse_json(raw)

        updated_items = []
        for index, update in enumerate(data.get("memory_updates", [])):
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
