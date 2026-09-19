from __future__ import annotations

import os
from statistics import mean, pstdev
from typing import Any

from threadaware.evaluations.runner import EvaluationRunner
from threadaware.providers.openai_provider import OpenAIProvider
from threadaware.scenarios.library import SCENARIOS
from threadaware.storage.runs import RunStore


class BatchRunner:
    def __init__(self, store: RunStore | None = None) -> None:
        self.store = store or RunStore()

    def run_repeated(
        self,
        *,
        scenario_id: str,
        repeats: int = 3,
        live: bool = False,
        max_turns: int | None = None,
    ) -> dict[str, Any]:
        configured_max = max(1, int(os.getenv("THREADAWARE_MAX_BATCH_RUNS", "25")))
        if repeats < 1 or repeats > configured_max:
            raise ValueError(f"repeats must be between 1 and {configured_max}")

        scenario = next((item for item in SCENARIOS if item.id == scenario_id), None)
        if scenario is None:
            raise ValueError("Scenario not found")

        provider = OpenAIProvider() if live else None
        runner = EvaluationRunner(provider=provider)
        saved_ids: list[str] = []
        results: list[dict[str, Any]] = []

        for _ in range(repeats):
            run = runner.run(scenario, live=live, max_turns=max_turns)
            payload = run.model_dump()
            run_id = self.store.save(
                payload,
                target_model=os.getenv("THREADAWARE_TARGET_MODEL") if live else None,
                auditor_model=os.getenv("THREADAWARE_AUDITOR_MODEL") if live else None,
                judge_model=os.getenv("THREADAWARE_JUDGE_MODEL") if live else None,
            )
            saved_ids.append(run_id)
            results.append(payload)

        dimensions = [
            "helpfulness",
            "appropriateness",
            "balanced_behavior",
            "context_adaptation",
            "continuity",
            "severity_awareness",
        ]
        stability: dict[str, Any] = {}
        for dimension in dimensions:
            values = [float(item["evaluation"][dimension]) for item in results]
            stability[dimension] = {
                "mean": mean(values),
                "stddev": pstdev(values) if len(values) > 1 else 0.0,
                "min": min(values),
                "max": max(values),
            }

        passed = [bool(item["evaluation"]["passed"]) for item in results]
        return {
            "scenario_id": scenario_id,
            "mode": "live" if live else "demo",
            "repeats": repeats,
            "run_ids": saved_ids,
            "pass_rate": sum(passed) / len(passed),
            "stability": stability,
        }
