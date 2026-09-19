from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from threadaware.paths import usage_ledger_path


class TokenBudgetExceeded(RuntimeError):
    pass


class TokenLedger:
    """Small local ledger for project-side API token accounting.

    This does not claim to know the provider-side grant balance. It records usage
    returned by API responses and enforces the configured local project ceiling.
    """

    _lock = threading.Lock()

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else usage_ledger_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def configured_budget(self) -> int:
        return max(1, int(os.getenv("THREADAWARE_TOTAL_TOKEN_BUDGET", "10000000")))

    def _empty(self) -> dict[str, Any]:
        return {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "calls": 0,
            "by_role": {},
            "by_model": {},
            "updated_at": None,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            data = self._read_unlocked()
        total = int(data.get("total_tokens", 0))
        return {
            **data,
            "configured_budget": self.configured_budget,
            "remaining_configured_budget": max(0, self.configured_budget - total),
            "budget_source": "project-side-ledger",
        }

    def ensure_available(self, reserved_output_tokens: int = 0) -> None:
        state = self.snapshot()
        if state["total_tokens"] >= self.configured_budget:
            raise TokenBudgetExceeded("ThreadAware project token budget has been exhausted.")
        if reserved_output_tokens > state["remaining_configured_budget"]:
            raise TokenBudgetExceeded(
                "Requested output allowance exceeds the remaining configured ThreadAware token budget."
            )

    def record(
        self,
        *,
        role: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int | None = None,
    ) -> dict[str, Any]:
        input_tokens = max(0, int(input_tokens or 0))
        output_tokens = max(0, int(output_tokens or 0))
        total_tokens = max(0, int(total_tokens if total_tokens is not None else input_tokens + output_tokens))

        with self._lock:
            data = self._read_unlocked()
            data["total_tokens"] = int(data.get("total_tokens", 0)) + total_tokens
            data["input_tokens"] = int(data.get("input_tokens", 0)) + input_tokens
            data["output_tokens"] = int(data.get("output_tokens", 0)) + output_tokens
            data["calls"] = int(data.get("calls", 0)) + 1

            by_role = data.setdefault("by_role", {})
            role_bucket = by_role.setdefault(role or "unspecified", {"total_tokens": 0, "calls": 0})
            role_bucket["total_tokens"] += total_tokens
            role_bucket["calls"] += 1

            by_model = data.setdefault("by_model", {})
            model_bucket = by_model.setdefault(model or "unknown", {"total_tokens": 0, "calls": 0})
            model_bucket["total_tokens"] += total_tokens
            model_bucket["calls"] += 1

            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

        return self.snapshot()

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else self._empty()
        except (OSError, json.JSONDecodeError):
            return self._empty()
