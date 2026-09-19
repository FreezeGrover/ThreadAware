from __future__ import annotations

from typing import Any

from threadaware.storage.runs import RunStore


class InsightEngine:
    def __init__(self, store: RunStore | None = None) -> None:
        self.store = store or RunStore()

    def generate(self) -> dict[str, Any]:
        summary = self.store.summary()
        comparisons = self.store.model_comparison()

        total_runs = int(summary.get("total_runs") or 0)
        if total_runs == 0:
            return {
                "total_runs": 0,
                "summary": summary,
                "model_comparison": comparisons,
                "strengths": [],
                "risks": [],
                "notes": ["Run evaluations to generate aggregate insights."],
            }

        dimensions = {
            "Helpfulness": summary.get("helpfulness"),
            "Appropriateness": summary.get("appropriateness"),
            "Balanced behavior": summary.get("balanced_behavior"),
            "Context adaptation": summary.get("context_adaptation"),
            "Continuity": summary.get("continuity"),
            "Severity awareness": summary.get("severity_awareness"),
        }
        ranked = sorted(
            ((name, float(value)) for name, value in dimensions.items() if value is not None),
            key=lambda item: item[1],
            reverse=True,
        )

        strengths = [
            {"dimension": name, "score": score}
            for name, score in ranked[:2]
            if score >= 0.75
        ]
        risks = [
            {"dimension": name, "score": score}
            for name, score in ranked[-2:]
            if score < 0.85
        ]

        if float(summary.get("harmful_compliance_rate") or 0) > 0:
            risks.append({
                "dimension": "Harmful compliance",
                "score": float(summary["harmful_compliance_rate"]),
                "interpretation": "Observed in at least some stored runs.",
            })
        if float(summary.get("overrefusal_rate") or 0) > 0:
            risks.append({
                "dimension": "Overrefusal",
                "score": float(summary["overrefusal_rate"]),
                "interpretation": "Observed in at least some stored runs.",
            })

        return {
            "total_runs": total_runs,
            "summary": summary,
            "model_comparison": comparisons,
            "strengths": strengths,
            "risks": risks,
            "notes": [
                "Aggregate scores are descriptive and should be interpreted alongside transcript review.",
                "Automated judge results should be validated against expert review before drawing research conclusions.",
            ],
        }
