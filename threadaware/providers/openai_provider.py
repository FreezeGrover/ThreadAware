from __future__ import annotations

import os

from openai import OpenAI

from threadaware.budget import TokenLedger
from threadaware.common.models import Turn
from threadaware.providers.base import ModelProvider


class OpenAIProvider(ModelProvider):
    def __init__(self, api_key: str | None = None, ledger: TokenLedger | None = None) -> None:
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.ledger = ledger or TokenLedger()

    def complete(
        self,
        *,
        model: str,
        messages: list[Turn],
        max_output_tokens: int = 1500,
        role: str = "unspecified",
    ) -> str:
        self.ledger.ensure_available(max_output_tokens)
        response = self.client.responses.create(
            model=model,
            input=[{"role": m.role, "content": m.content} for m in messages],
            max_output_tokens=max_output_tokens,
        )

        usage = getattr(response, "usage", None)
        if usage is not None:
            input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
            total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
            self.ledger.record(
                role=role,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )

        return response.output_text
