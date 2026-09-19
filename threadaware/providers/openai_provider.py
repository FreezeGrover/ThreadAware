from __future__ import annotations

import os
from openai import OpenAI

from threadaware.common.models import Turn
from threadaware.providers.base import ModelProvider


class OpenAIProvider(ModelProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def complete(
        self,
        *,
        model: str,
        messages: list[Turn],
        max_output_tokens: int = 1500,
    ) -> str:
        response = self.client.responses.create(
            model=model,
            input=[{"role": m.role, "content": m.content} for m in messages],
            max_output_tokens=max_output_tokens,
        )
        return response.output_text
