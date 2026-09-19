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
                f"The conversation has moved toward {topic}."
                if relation == "new"
                else f"The focus has shifted while still connecting with what came before."
            )
            noticing.append({"kind": "topic-shift", "title": "Current intent", "note": acknowledgement, "importance": "normal"})
        elif not previous:
            relation = "new"
            noticing.append({"kind": "connection", "title": "Current intent", "note": f"The conversation is beginning around {topic}.", "importance": "quiet"})
        else:
            noticing.append({"kind": "connection", "title": "Current intent", "note": f"The user is continuing around {topic}.", "importance": "quiet"})

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
            noticing.append({"kind": "possible-interpretations", "title": "Needs clarification", "note": "There is more than one reasonable reading, so choosing one without checking could change the answer.", "importance": "normal"})

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

        prompt = f"""You are ThreadAware's conversation-understanding layer.

Analyze the latest user turn against the ENTIRE visible conversation and active ThreadAware memory.
Do not reveal hidden chain-of-thought. Return only concise, user-safe conclusions about what the user is doing now and what still matters from earlier.

The central principle is CONTINUITY, not simple topic-change detection.
A new topic does not erase an unresolved important thread. In particular, wellbeing, health, safety, acute distress, medication, self-care, or risk-related information can remain important even when the user abruptly moves to something casual.

For every turn, distinguish:
- CURRENT INTENT: what the user appears to want or do right now.
- CARRIED-FORWARD THREADS: earlier matters that remain unresolved or materially relevant.
- PRIORITY: whether any carried-forward wellbeing/safety issue deserves continued attention.

WELLBEING / SAFETY CONTINUITY RULES:
- If the user previously disclosed an unresolved health, wellbeing, or safety concern, do NOT silently drop it merely because they changed topics.
- Keep such a concern active until the conversation provides reasonable evidence that it is resolved, no longer relevant, or superseded.
- When the user pivots away from an unresolved wellbeing/safety concern, produce a separate noticing item with kind="sensitivity" and importance="high" or "normal" depending on seriousness.
- That notice should say plainly what remains important, without alarming the user or hijacking the new topic.
- Do not nag. The purpose is to preserve situational awareness, not force the conversation back.
- If a safety-critical detail would materially change what the assistant should do next, make that importance visible.

CURRENT-INTENT RULES:
- Produce one noticing item that summarizes the user's present intent in plain language.
- Do not copy the user's raw words as the title. For example, a message like "hiiii" should be summarized with a neutral label such as "Greeting" or "Check-in", not repeated verbatim.
- A greeting is not automatically a topic shift.
- If there is no concrete request yet, say that naturally rather than inventing one.

OTHER THINGS TO TRACK:
1. Goals, priorities, constraints, decisions, corrections, and details that modify earlier information.
2. Unanswered assistant questions that still matter.
3. Returns to earlier threads.
4. More than one reasonable interpretation when it genuinely affects the answer. Call these possible interpretations or possible readings.
5. Connections between current intent and older context.

NOTICING VOICE:
- Write like a warm, perceptive companion, not a classifier, event log, analyst, or clinical dashboard.
- Use short human-readable titles such as "Greeting", "Current intent", "Health concern", "Open question", "Returning thread", or another natural label that fits the actual turn.
- Notes should usually be one natural sentence; two short sentences only when useful.
- Never expose internal category names or taxonomy phrases.
- Do not mechanically say "we moved from X to Y".
- Do not repeatedly use stock closings such as "keeping both threads in view".
- Do not begin with filler such as "Hmm", "Oh", "Interesting", "Aha", or "Well".
- Do not repeat the same sentence skeleton across adjacent turns.
- Do not overstate tiny shifts.
- Never sound clinical, bureaucratic, or robotic.
- Do not invent feelings, motives, diagnoses, or facts.
- Keep each note concise enough to scan quickly, ideally under 35 words.

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
- EVERY user turn must yield at least one noticing item summarizing current intent.
- Add a separate carried-forward notice whenever an unresolved earlier thread remains important enough to affect future support.
- Unresolved wellbeing/safety concerns should survive unrelated topic changes.
- If the current turn genuinely resolves an earlier concern, stop carrying it forward.
- Add more than two notices only when clearly necessary.
- If the user returns to an old topic, use relation="returning" internally but phrase the note naturally.
- If the latest turn answers an earlier open question, stop describing it as unanswered.

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
            max_output_tokens=1800,
        )
        data = self._parse_json(raw)

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
        prompt = f"""You are ThreadAware's noticing layer.

The structural conversation analysis returned no noticing items. Generate the missing user-safe awareness trace now.

You MUST return at least one event summarizing the latest user's CURRENT INTENT, even for a greeting, check-in, joke, continuation, or ordinary question.

Also inspect the entire transcript and memory for unresolved wellbeing, health, safety, distress, medication, or risk-related threads. If one remains unresolved and could still matter, add a separate sensitivity notice so it is not lost just because the user changed topics.

VOICE:
- Use a short natural title such as "Greeting", "Current intent", "Health concern", "Open question", or another human-readable label.
- Do not copy raw user text as a title.
- Usually write one natural sentence per notice, ideally under 35 words.
- Do not use taxonomy labels, mechanical transition language, stock closings, or filler interjections.
- Do not invent motives, emotions, diagnoses, or facts.
- Do not expose hidden reasoning.

Return JSON only:
{{
  "noticing": [{{
    "kind": "topic-shift"|"return"|"goal-change"|"priority-change"|"constraint"|"sensitivity"|"open-question"|"possible-interpretations"|"memory-update"|"connection"|"other",
    "title": string,
    "note": string,
    "importance": "quiet"|"normal"|"high"
  }}]
}}

Existing analysis:
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
                max_output_tokens=650,
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
            "health and wellbeing": ["health", "sleep", "tired", "doctor", "pain", "stress", "cough", "coughing", "medicine", "medication"],
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
