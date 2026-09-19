from __future__ import annotations

import json
import re
from typing import Any

from threadaware.common.models import Turn
from threadaware.memory.engine import ConversationMemory
from threadaware.memory.models import ConversationUnderstanding, WellbeingThreadState
from threadaware.providers.base import ModelProvider


class ConversationUnderstandingEngine:
    """Longitudinal conversation understanding with a user-safe wellbeing lifecycle."""

    HEALTH_TOPIC = "health and wellbeing"
    HEALTH_SIGNALS = {
        "health", "symptom", "symptoms", "sick", "ill", "illness", "pain", "hurt", "injury",
        "fever", "cough", "coughing", "breathing", "breath", "wheezing", "dizzy", "dizziness",
        "nausea", "vomiting", "headache", "migraine", "rash", "bleeding", "infection", "allergy",
        "medicine", "medication", "drug", "doctor", "hospital", "sleep", "insomnia", "stress",
        "anxiety", "anxious", "panic", "depressed", "depression", "distress", "self-harm",
        "suicidal", "eating", "appetite", "pregnant", "pregnancy", "wellbeing", "well-being",
    }

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
        topic = self._coarse_topic(latest.lower())
        previous = self.active_topic
        shifted = bool(previous and topic != previous)
        relation = "new" if shifted or not previous else "same"
        acknowledgement = f"The conversation has moved toward {topic}." if shifted else None
        noticing = [self._current_intent_notice(latest, topic)]

        self.active_topic = topic
        memory_item = self.memory.upsert(
            topic=topic,
            summary=latest[:240] or "Conversation topic introduced",
            detail=latest or None,
            source_turn=max(0, len(turns) - 1),
        )

        interpretations: list[dict[str, Any]] = []
        clarification_needed = False
        clarification_question = None
        reason = "The latest turn has one sufficiently clear operational reading."
        if self._has_competing_demo_readings(turns):
            candidates = self._candidate_referent_labels(turns)
            first = candidates[0] if candidates else "the first recent item"
            second = candidates[1] if len(candidates) > 1 else "the other recent item"
            interpretations = [
                {"label": f"{first} reading", "description": f"The request may refer to {first}.", "confidence": 0.5, "evidence": []},
                {"label": f"{second} reading", "description": f"The request may instead refer to {second}.", "confidence": 0.5, "evidence": []},
            ]
            clarification_needed = True
            clarification_question = f"When you say that, do you mean {first}, or {second}?"
            reason = "More than one plausible reading survives and choosing one could materially change the response."

        self._enforce_wellbeing_lifecycle(turns, topic, noticing, model_state=None)
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

    def _analyze_live(self, turns: list[Turn]) -> ConversationUnderstanding:
        transcript = "\n".join(f"{turn.role}: {turn.content}" for turn in turns)
        memories = [item.model_dump() for item in self.memory.active()]
        prior_wellbeing = self.wellbeing_state.model_dump()

        prompt = f"""You are ThreadAware's conversation-understanding layer.
Analyze the latest user turn against the ENTIRE visible conversation, active memory, and prior wellbeing state.
Return only concise user-safe JSON; never reveal hidden reasoning.

Core rule: continuity survives topic changes. Later information can update, correct, resolve, supersede, increase, or decrease the importance of earlier information even after many unrelated turns.

For EVERY turn identify:
1. CURRENT INTENT — what the USER is doing or asking now. Never summarize the assistant's own reply as the user's intent.
2. CARRIED-FORWARD THREADS — unresolved matters that still affect future support.
3. WELLBEING STATE — any physical health, mental health, medication, distress, eating-related, sleep, injury, symptom, or safety concern. This is semantic: do not rely on a fixed list of diagnoses.

Wellbeing lifecycle:
- Never drop an unresolved concern merely because the user changes topic.
- Update the same concern when later information refers back to it, even after a long detour.
- If newer information corrects an old detail, use the newer detail in the current summary.
- Mark resolved only when there is evidence of resolution.
- Increase/decrease severity when evidence changes.
- Track important unanswered questions.
- On the first meaningful pivot away from an unresolved concern, set should_follow_up_now=true when one key missing fact still materially affects safe/helpful support.
- After that follow-up is attempted and the user still does not answer, move to waiting/monitoring instead of repeating it every turn, unless new evidence raises risk or a natural reopening makes another follow-up useful.
- Silence or topic change alone is never evidence of emergency.
- Ask for the minimum information needed.

Noticing voice:
- Every user turn gets a current-intent notice.
- A casual greeting should be represented semantically, e.g. "Casual greeting / social check-in", not by copying either speaker's words.
- If wellbeing remains unresolved, add a separate sensitivity/open-question notice.
- Say "not answered yet" or "still unresolved", never "dodged" unless the user explicitly says they intentionally avoided it.

Return JSON exactly in this shape:
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

        raw_wellbeing = data.get("wellbeing")
        try:
            model_state = WellbeingThreadState.model_validate(raw_wellbeing) if isinstance(raw_wellbeing, dict) else None
        except Exception:
            model_state = None

        topic = data.get("active_topic") or self._coarse_topic(turns[-1].content.lower())
        noticing = data.get("noticing") if isinstance(data.get("noticing"), list) else []
        noticing = self._normalize_current_intent(turns, noticing, topic)
        self._enforce_wellbeing_lifecycle(turns, topic, noticing, model_state=model_state)
        data["noticing"] = noticing
        data["wellbeing"] = self.wellbeing_state.model_dump()

        updated_items = []
        for update in data.get("memory_updates", []):
            if not isinstance(update, dict) or not update.get("topic") or not update.get("summary"):
                continue
            item = self.memory.upsert(
                topic=str(update["topic"]),
                summary=str(update["summary"]),
                detail=update.get("detail"),
                source_turn=max(0, len(turns) - 1),
            )
            updated_items.append(item.model_dump())

        # Always retain the latest user turn in memory even if the model omitted a memory update.
        if not updated_items and turns:
            item = self.memory.upsert(
                topic=topic,
                summary=turns[-1].content[:240],
                detail=turns[-1].content,
                source_turn=max(0, len(turns) - 1),
            )
            updated_items.append(item.model_dump())

        data["memory_updates"] = updated_items
        self.active_topic = topic or self.active_topic
        return ConversationUnderstanding.model_validate(data)

    def _enforce_wellbeing_lifecycle(
        self,
        turns: list[Turn],
        topic: str | None,
        noticing: list[dict[str, Any]],
        model_state: WellbeingThreadState | None,
    ) -> None:
        """Repair lifecycle state when the semantic model under-tracks an established concern."""
        prior = self.wellbeing_state.model_copy(deep=True)
        latest = turns[-1].content.strip() if turns else ""
        latest_lower = latest.lower()
        latest_is_health = topic == self.HEALTH_TOPIC or self._contains_health_signal(latest_lower)
        health_memory = self._latest_health_memory()

        if model_state is not None:
            next_state = model_state.model_copy(deep=True)
        else:
            next_state = prior.model_copy(deep=True)

        # A previously established concern cannot disappear just because a later model call omitted it.
        if prior.active and next_state.status != "resolved":
            next_state.active = True
            next_state.follow_up_attempts = max(prior.follow_up_attempts, next_state.follow_up_attempts)
            if not next_state.summary:
                next_state.summary = prior.summary
            if not next_state.key_missing_info:
                next_state.key_missing_info = list(prior.key_missing_info)
            if not next_state.recommended_action:
                next_state.recommended_action = prior.recommended_action

        # Fallback activation: semantic model or topic memory established a health/wellbeing concern.
        if not next_state.active and next_state.status != "resolved" and (latest_is_health or health_memory):
            source_summary = None
            if latest_is_health and latest:
                source_summary = latest[:220]
            elif health_memory:
                source_summary = health_memory.summary
            next_state = WellbeingThreadState(
                active=True,
                summary=source_summary or "A health or wellbeing concern remains active.",
                status="needs-clarification",
                severity="unknown",
                key_missing_info=["enough context to judge severity and the safest next step"],
                follow_up_attempts=0,
                should_follow_up_now=False,
                recommended_action="Gather the minimum important facts and adjust support to the evidence.",
                user_safe_note="This health or wellbeing concern is still unresolved.",
            )

        # If the previous turn required a follow-up, the response layer was explicitly instructed to ask it.
        # On the next user turn, count that attempt and stop immediate repetition unless new risk warrants it.
        if prior.active and prior.should_follow_up_now and next_state.status != "resolved":
            next_state.follow_up_attempts = max(next_state.follow_up_attempts, prior.follow_up_attempts + 1)
            next_state.status = "waiting"
            next_state.should_follow_up_now = False

        # First meaningful pivot away from an unresolved concern: ask once, gently.
        if next_state.active and next_state.status != "resolved" and not latest_is_health:
            if prior.active and not prior.should_follow_up_now and prior.follow_up_attempts == 0:
                next_state.should_follow_up_now = True
                next_state.status = "follow-up-asked"
                next_state.recommended_action = "Answer the current request, then gently ask one important unresolved wellbeing question."
            elif next_state.follow_up_attempts > 0:
                next_state.should_follow_up_now = False
                if next_state.status not in {"professional-care", "urgent", "emergency"}:
                    next_state.status = "waiting"

        # Do not treat absence of a recent mention as resolution.
        if next_state.status == "resolved":
            next_state.active = False
            next_state.should_follow_up_now = False
            next_state.key_missing_info = []

        self.wellbeing_state = next_state
        self._ensure_wellbeing_notices(noticing)

    def _ensure_wellbeing_notices(self, noticing: list[dict[str, Any]]) -> None:
        state = self.wellbeing_state
        if not state.active or state.status == "resolved":
            return

        has_health = any(
            isinstance(event, dict) and event.get("kind") == "sensitivity"
            for event in noticing
        )
        if not has_health:
            noticing.append({
                "kind": "sensitivity",
                "title": "Health / wellbeing",
                "note": state.user_safe_note or state.summary or "An earlier wellbeing concern is still unresolved.",
                "importance": "high" if state.severity in {"high", "urgent"} else "normal",
            })

        if state.key_missing_info and not any(
            isinstance(event, dict) and event.get("kind") == "open-question"
            for event in noticing
        ):
            missing = state.key_missing_info[0]
            note = (
                f"Still need {missing}. I’ll ask once more gently because it could change the safest next step."
                if state.should_follow_up_now
                else f"Still unresolved: {missing}. I’ll keep it in view without repeating the same question every turn."
            )
            noticing.append({
                "kind": "open-question",
                "title": "Health follow-up",
                "note": note,
                "importance": "normal",
            })

    def _normalize_current_intent(
        self,
        turns: list[Turn],
        noticing: list[dict[str, Any]],
        topic: str | None,
    ) -> list[dict[str, Any]]:
        latest = turns[-1].content.strip() if turns else ""
        assistants = {turn.content.strip() for turn in turns if turn.role == "assistant"}
        current_candidates = [
            event for event in noticing
            if isinstance(event, dict) and event.get("kind") in {"connection", "topic-shift", "return"}
        ]

        if self._is_greeting(latest):
            replacement = {
                "kind": "connection",
                "title": "Current intent",
                "note": "Casual greeting / social check-in.",
                "importance": "quiet",
            }
            noticing = [event for event in noticing if event not in current_candidates]
            noticing.insert(0, replacement)
            return noticing

        # Never let the user's current-intent card simply repeat an assistant message.
        for event in current_candidates:
            if str(event.get("note", "")).strip() in assistants:
                event["title"] = "Current intent"
                event["note"] = self._semantic_intent_fallback(latest, topic)
                event["importance"] = "quiet"

        if not current_candidates:
            noticing.insert(0, {
                "kind": "connection",
                "title": "Current intent",
                "note": self._semantic_intent_fallback(latest, topic),
                "importance": "quiet",
            })
        return noticing

    @staticmethod
    def _semantic_intent_fallback(latest: str, topic: str | None) -> str:
        text = latest.strip()
        lower = text.lower()
        if any(word in lower for word in ("movie", "cinema", "film")):
            return "Wants to choose or talk about a movie."
        if text.endswith("?"):
            return "Asking a question about the current topic."
        if topic:
            return f"Continuing with {topic}."
        return "Continuing the conversation."

    @staticmethod
    def _is_greeting(text: str) -> bool:
        normalized = re.sub(r"[^a-z\s']", " ", text.lower()).strip()
        return bool(re.fullmatch(r"(?:hey|hi|hello|hii+|heyy+|good morning|good afternoon|good evening)(?:\s+how are you)?", normalized))

    def _latest_health_memory(self):
        matches = [item for item in self.memory.active() if item.topic == self.HEALTH_TOPIC]
        return matches[-1] if matches else None

    def _contains_health_signal(self, text: str) -> bool:
        tokens = set(re.findall(r"[a-z]+(?:-[a-z]+)?", text.lower()))
        return bool(tokens & self.HEALTH_SIGNALS)

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

    @staticmethod
    def _current_intent_notice(latest: str, topic: str) -> dict[str, str]:
        if ConversationUnderstandingEngine._is_greeting(latest):
            return {"kind": "connection", "title": "Current intent", "note": "Casual greeting / social check-in.", "importance": "quiet"}
        return {"kind": "connection", "title": "Current intent", "note": ConversationUnderstandingEngine._semantic_intent_fallback(latest, topic), "importance": "quiet"}

    def _coarse_topic(self, text: str) -> str:
        if self._contains_health_signal(text):
            return self.HEALTH_TOPIC
        groups = {
            "travel planning": ["trip", "travel", "flight", "hotel", "japan", "city"],
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
