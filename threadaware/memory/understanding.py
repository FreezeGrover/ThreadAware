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
                f"The conversation has moved from {previous} toward {topic}."
                if relation == "new"
                else f"The focus has moved toward {topic}, while still connecting with what came before."
            )
            noticing.append({"kind": "topic-shift", "title": "Shift", "note": acknowledgement, "importance": "normal"})
        elif not previous:
            relation = "new"
            noticing.append({"kind": "connection", "title": "Opening", "note": f"The conversation is beginning around {topic}.", "importance": "quiet"})
        else:
            noticing.append({"kind": "connection", "title": "Continuing", "note": f"This continues the current thread around {topic}.", "importance": "quiet"})

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

        if self._has_competing_demo_readings(turns):
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
            noticing.append({"kind": "possible-interpretations", "title": "Possible readings", "note": "There is more than one reasonable way to read that, so choosing one without checking could change the answer.", "importance": "normal"})

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
    def _has_competing_demo_readings(turns: list[Turn]) -> bool:
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
        # conversation: aware of a change, a return, an unanswered thread, or simply the
        # tone and direction of an ordinary turn. The wording must always be freshly
        # generated from the actual conversation and must never rotate stock phrases.
        prompt = f"""You are ThreadAware's conversation-understanding layer.

Analyze the latest user turn against the entire visible conversation and ThreadAware memory.
Do not reveal hidden chain-of-thought. Create a short, user-safe observation about what matters in the conversation right now and what should remain in view.

Track carefully:
1. The current topic and whether the user continued it, changed it, or returned to an earlier one.
2. Goals, priorities, constraints, decisions, corrections, and details that modify earlier information.
3. Changes in sensitivity, urgency, wellbeing, or risk.
4. More than one reasonable interpretation when it genuinely matters. Describe these as possible interpretations or possible readings.
5. Questions the assistant asked that the user did not answer. Keep them as open threads without nagging.
6. Repeated or revisited ideas. Treat a return as a return, not as brand-new information.
7. Connections between older threads and the current turn.
8. Ordinary conversational movement too, including greetings, check-ins, jokes, small pivots, and continuations.

NOTICING VOICE — THIS MATTERS A LOT:
- Produce at least one noticing item for EVERY user turn, including a greeting or an ordinary continuation.
- Write the note as if a warm, perceptive companion were quietly keeping the thread, not as a classifier, dashboard, event log, or analyst.
- The note should usually be ONE natural sentence. Two short sentences are fine when genuinely useful.
- Prefer ordinary conversational words. Never expose internal category names, taxonomies, labels, or phrases such as "casual greeting and wellbeing check-in", "bat ownership question", "topic A", or "topic B".
- Do not mechanically narrate transitions as "We moved from X to Y". Describe the human meaning of the turn instead.
- Do not repeatedly say that you are "keeping both threads in view", "keeping the earlier thread in mind", "following along", or equivalent stock phrases.
- Do not begin notes or titles with filler interjections such as "Hmm", "Oh", "Interesting", "Aha", or "Well".
- Do not use the same opening, sentence skeleton, or closing across adjacent notices. Read the previous conversation and vary naturally.
- A greeting is not automatically a topic change. Treat greetings and check-ins lightly unless they genuinely alter the conversation.
- Do not overstate tiny shifts. Sometimes the right observation is simply that the user is continuing, checking in, joking, or opening a new question.
- You may be lightly playful in casual contexts, but never force humor and never use playful language for serious or sensitive moments.
- Do not invent feelings, motives, or facts.
- Never sound clinical, diagnostic, bureaucratic, or robotic.
- Do not expose private reasoning steps. Show only the concise conclusion of what was noticed.
- The title is metadata for the interface and is not shown prominently. Keep it neutral and very short (1–3 words). Put the natural language in the note.

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
- Add more than one only when two genuinely different things matter; do not split one thought into multiple cards.
- If an earlier assistant question remains unanswered, preserve it only when it still matters naturally.
- If the latest turn answers it, stop describing it as unanswered.
- If an old topic returns, use relation="returning" internally, but phrase the note naturally rather than announcing a classification.
- If a previous goal or priority changes, describe what changed in plain language.
- If a new constraint appears, describe its practical effect rather than merely labeling it a constraint.
- Keep each note concise enough to read at a glance, ideally under 35 words.

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

        # Some live models can complete the structural analysis yet omit a notice on an
        # ordinary turn. In that case a second, narrowly-scoped generative pass supplies
        # the conversation-specific observation. Nothing is selected from canned text.
        if not data.get("noticing"):
            data["noticing"] = self._generate_live_noticing(
                transcript=transcript,
                analysis=data,
                memories=memories,
            )

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

    def _generate_live_noticing(
        self,
        *,
        transcript: str,
        analysis: dict[str, Any],
        memories: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate at least one fresh, user-safe noticing event when the main pass omitted it."""
        prompt = f"""You are ThreadAware's noticing layer.

The structural conversation analysis returned no noticing item. Write the missing observation for the latest user turn.

You MUST return at least one event, even when the latest turn is only a greeting, check-in, joke, continuation, or ordinary question.

VOICE:
- Write like a warm, perceptive companion quietly following the conversation.
- Usually write one natural sentence, ideally under 35 words.
- Use ordinary human language, never internal category names or taxonomy labels from the analysis.
- Do not mechanically say "we moved from X to Y".
- Do not use stock closings about "keeping both threads in view" or "keeping the earlier thread in mind".
- Do not begin with "Hmm", "Oh", "Interesting", "Aha", or similar filler.
- Do not reuse a sentence pattern merely because it worked on an earlier turn.
- A greeting or check-in is not automatically a topic shift.
- Do not invent motives, emotions, or facts.
- Do not expose hidden reasoning.
- Keep the title neutral and very short; the note carries the natural wording.

Return JSON only:
{{
  "noticing": [{{
    "kind": "topic-shift"|"return"|"goal-change"|"priority-change"|"constraint"|"sensitivity"|"open-question"|"possible-interpretations"|"memory-update"|"connection"|"other",
    "title": string,
    "note": string,
    "importance": "quiet"|"normal"|"high"
  }}]
}}

Existing analysis (use it for facts, but do not copy its category labels into the note):
{json.dumps(analysis, indent=2)}

Existing ThreadAware memory:
{json.dumps(memories, indent=2)}

Full visible transcript:
{transcript}
"""

        for _ in range(2):
            raw = self.provider.complete(
                model=self.model,
                messages=[Turn(role="user", content=prompt)],
                max_output_tokens=500,
            )
            try:
                payload = self._parse_json(raw)
            except (ValueError, json.JSONDecodeError):
                continue
            events = payload.get("noticing")
            if isinstance(events, list) and any(
                isinstance(event, dict) and event.get("title") and event.get("note")
                for event in events
            ):
                return events
        return []

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
