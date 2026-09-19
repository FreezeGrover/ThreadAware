from __future__ import annotations

import json
import re
from typing import Any

from threadaware.common.models import Turn
from threadaware.memory.engine import ConversationMemory
from threadaware.memory.models import ConversationUnderstanding, WellbeingThreadState
from threadaware.providers.base import ModelProvider


class ConversationUnderstandingEngine:
    """Analyze how a conversation evolves without prematurely collapsing uncertainty."""

    def __init__(self, provider: ModelProvider | None = None, model: str | None = None) -> None:
        self.provider = provider
        self.model = model
        self.memory = ConversationMemory()
        self.active_topic: str | None = None
        self.wellbeing_state = WellbeingThreadState()

    def analyze(self, *, turns: list[Turn], live: bool = False) -> ConversationUnderstanding:
        if live and self.provider and self.model:
            return self._analyze_live(turns)
        return self._analyze_demo(turns)

    def clear(self) -> None:
        self.memory = ConversationMemory()
        self.active_topic = None
        self.wellbeing_state = WellbeingThreadState()

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
                else "The focus has shifted while still connecting with what came before."
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
            "wellbeing": self.wellbeing_state.model_dump(),
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
        prior_wellbeing = self.wellbeing_state.model_dump()

        prompt = f"""You are ThreadAware's conversation-understanding layer.

Analyze the latest user turn against the ENTIRE visible conversation, active ThreadAware memory, and the prior wellbeing-thread state.
Do not reveal hidden chain-of-thought. Return only concise, user-safe conclusions and structured state.

The central principle is CONTINUITY.
A topic change must not erase earlier information that still matters. Later turns may UPDATE, CORRECT, RESOLVE, SUPERSEDE, or INCREASE the importance of earlier details, even after many unrelated turns.

For every turn distinguish:
- CURRENT INTENT: what the user wants now.
- CARRIED-FORWARD THREADS: earlier matters that remain relevant.
- WELLBEING STATE: whether any health/wellbeing/safety concern remains active, what information is still missing, whether a follow-up is due, and whether the concern has become more or less serious.

GENERIC WELLBEING LIFECYCLE:
- Apply this to any physical-health, mental-health, medication, distress, eating-related, sleep, injury, symptom, or safety-relevant concern. Do not special-case one symptom.
- If a concern was previously active, do not silently drop it because the user changes topic.
- Update the SAME thread when later information refers back to it, even after long detours.
- If newer information corrects an earlier detail, the newer detail should replace the outdated assumption in the summary while provenance remains available in conversation memory.
- If the user clearly says the concern is resolved, recovered, no longer relevant, or a clinician has clarified it, mark the state resolved when appropriate.
- If later evidence makes the situation more concerning, increase severity and update the recommended action.
- If later evidence makes it less concerning, de-escalate proportionately.

FOLLOW-UP POLICY:
- Track whether an important wellbeing question was asked and whether the user answered it.
- follow_up_attempts counts distinct assistant attempts to obtain the key missing information for the ACTIVE concern, not ordinary turns.
- should_follow_up_now=true when one important unanswered question should be gently asked in the next response.
- On the first meaningful pivot away from an unresolved concern, a single gentle follow-up is normally appropriate if the missing information affects safe/helpful support.
- If that follow-up has already been asked and the user again moves on, do not request the same information every turn. Set status to waiting or monitoring and should_follow_up_now=false unless new evidence raises concern or a natural reopening makes another follow-up useful.
- Silence or a topic change by itself is NOT evidence of an emergency.
- If the latest user turn answers a previously missing item, remove that item from key_missing_info and update status/action accordingly.
- Ask for the minimum information needed; do not turn the conversation into an interrogation.

NOTICING:
- EVERY user turn needs at least one noticing item for current intent.
- When an unresolved wellbeing thread remains relevant, add a separate sensitivity or open-question notice.
- Use warm, human-readable language such as "Health concern", "Wellbeing check-in", "Open question", "Still unresolved", "Updated health context", or similar.
- Never say the user "dodged" or "ignored" a question unless the user explicitly says they intentionally did so. Prefer "not answered yet" or "still unresolved".
- Do not expose internal taxonomy or hidden reasoning.

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
  }}],
  "wellbeing": {{
    "active": boolean,
    "summary": string|null,
    "status": "none"|"needs-clarification"|"follow-up-asked"|"waiting"|"monitoring"|"professional-care"|"urgent"|"emergency"|"resolved",
    "severity": "unknown"|"low"|"moderate"|"high"|"urgent",
    "key_missing_info": [string],
    "follow_up_attempts": integer,
    "should_follow_up_now": boolean,
    "recommended_action": string|null,
    "user_safe_note": string|null
  }}
}}

Additional rules:
- Preserve the prior wellbeing state unless the transcript gives a reason to update it.
- Do not reset follow_up_attempts just because the topic changed.
- Do not mark an issue resolved merely because it has not been mentioned recently.
- If no wellbeing concern has appeared, return the neutral default state.
- If the current turn genuinely resolves the concern, active may become false and status="resolved".
- Keep summaries compact but specific enough to reconnect after many twists and turns.

Prior wellbeing state:
{json.dumps(prior_wellbeing, indent=2)}

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
            max_output_tokens=2000,
        )
        data = self._parse_json(raw)

        if not data.get("noticing"):
            data["noticing"] = self._generate_live_noticing(
                transcript=transcript,
                analysis=data,
                memories=memories,
            )

        raw_wellbeing = data.get("wellbeing")
        if isinstance(raw_wellbeing, dict):
            try:
                next_wellbeing = WellbeingThreadState.model_validate(raw_wellbeing)
            except Exception:
                next_wellbeing = self.wellbeing_state.model_copy(deep=True)
        else:
            next_wellbeing = self.wellbeing_state.model_copy(deep=True)

        if self.wellbeing_state.active and next_wellbeing.status != "resolved":
            next_wellbeing.follow_up_attempts = max(
                self.wellbeing_state.follow_up_attempts,
                next_wellbeing.follow_up_attempts,
            )
            if not next_wellbeing.summary:
                next_wellbeing.summary = self.wellbeing_state.summary
            if not next_wellbeing.key_missing_info:
                next_wellbeing.key_missing_info = list(self.wellbeing_state.key_missing_info)

        self.wellbeing_state = next_wellbeing
        data["wellbeing"] = self.wellbeing_state.model_dump()

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

You MUST return at least one event summarizing the latest user's CURRENT INTENT.
Also inspect the entire transcript, memory, and wellbeing state for unresolved health, wellbeing, safety, distress, medication, or risk-related threads. If one remains relevant, add a separate sensitivity/open-question notice.

Use short natural titles. Do not copy raw user text as a title. Do not invent motives, diagnoses, or facts. Do not expose hidden reasoning.

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

Prior wellbeing state:
{json.dumps(self.wellbeing_state.model_dump(), indent=2)}

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
