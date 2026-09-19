from __future__ import annotations

from abc import ABC, abstractmethod
from threadaware.common.models import Turn


class ModelProvider(ABC):
    @abstractmethod
    def complete(
        self,
        *,
        model: str,
        messages: list[Turn],
        max_output_tokens: int = 1500,
    ) -> str:
        raise NotImplementedError
