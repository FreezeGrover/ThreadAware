from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
from uuid import uuid4

from threadaware.memory.models import MemoryItem


class ConversationMemory:
    """Adaptive conversation memory for dialogue continuity across time.

    Memory items are topic-based summaries that can be updated when later turns
    add linked information. This is intentionally not a formal world-state model.
    """

    def __init__(self) -> None:
        self.items: list[MemoryItem] = []

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

    def find_related(self, topic: str, threshold: float = 0.45) -> MemoryItem | None:
        candidates = [
            (self._similarity(topic, item.topic), item)
            for item in self.items
            if item.status == "active"
        ]
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        if candidates and candidates[0][0] >= threshold:
            return candidates[0][1]
        return None

    def upsert(
        self,
        *,
        topic: str,
        summary: str,
        detail: str | None = None,
        source_turn: int | None = None,
    ) -> MemoryItem:
        now = datetime.now(timezone.utc).isoformat()
        existing = self.find_related(topic)
        if existing:
            existing.topic = topic
            existing.summary = summary
            if detail and detail not in existing.details:
                existing.details.append(detail)
            if source_turn is not None and source_turn not in existing.source_turns:
                existing.source_turns.append(source_turn)
            existing.updated_at = now
            return existing

        item = MemoryItem(
            id=str(uuid4()),
            topic=topic,
            summary=summary,
            details=[detail] if detail else [],
            source_turns=[source_turn] if source_turn is not None else [],
        )
        self.items.append(item)
        return item

    def mark_resolved(self, topic: str) -> MemoryItem | None:
        item = self.find_related(topic)
        if item:
            item.status = "resolved"
            item.updated_at = datetime.now(timezone.utc).isoformat()
        return item

    def active(self) -> list[MemoryItem]:
        return [item.model_copy(deep=True) for item in self.items if item.status == "active"]

    def snapshot(self) -> list[MemoryItem]:
        return [item.model_copy(deep=True) for item in self.items]
