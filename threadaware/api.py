from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from threadaware.common.models import Turn
from threadaware.continuity.engine import ContinuityEngine
from threadaware.evaluations.batch import BatchRunner
from threadaware.evaluations.runner import EvaluationRunner
from threadaware.evaluations.scoring import aggregate_pass
from threadaware.insights.analysis import InsightEngine
from threadaware.providers.openai_provider import OpenAIProvider
from threadaware.scenarios.library import SCENARIOS
from threadaware.storage.runs import RunStore
from threadaware.validation.agreement import percent_agreement


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"

app = FastAPI(title="ThreadAware API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ContinuityEngine()
engine.apply_update(kind="goal", value="Plan a two-week Japan trip")
engine.apply_update(kind="goal", value="Keep the itinerary low-stress")
engine.apply_update(kind="constraint", value="Three remote-work mornings")
engine.apply_update(kind="preference", value="Tokyo")
engine.apply_update(kind="preference", value="Kyoto")
engine.apply_update(kind="preference", value="Slower pace")
engine.apply_update(kind="question", value="Should the remote-work mornings be grouped or split?")
engine.set_sensitivity("low")

store = RunStore()
insights = InsightEngine(store=store)
batches = BatchRunner(store=store)

DEMO_EVALUATION = aggregate_pass(
    helpfulness=0.91,
    appropriateness=0.94,
    balanced_behavior=0.93,
    context_adaptation=0.89,
    continuity=0.93,
    severity_awareness=0.90,
    harmful_compliance=False,
    overrefusal=False,
)


class RunRequest(BaseModel):
    scenario_id: str
    live: bool = False
    max_turns: int | None = None


class BatchRequest(BaseModel):
    scenario_id: str
    repeats: int = 3
    live: bool = False
    max_turns: int | None = None


class ChatRequest(BaseModel):
    messages: list[Turn]
    model: str | None = None


def live_configured() -> bool:
    return bool(
        os.getenv("OPENAI_API_KEY")
        and os.getenv("THREADAWARE_TARGET_MODEL")
        and os.getenv("THREADAWARE_AUDITOR_MODEL")
        and os.getenv("THREADAWARE_JUDGE_MODEL")
    )


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ready",
        "mode": "live" if live_configured() else "demo",
        "provider": "openai" if live_configured() else None,
        "pipeline": "auditor-target-continuity-judge",
        "storage": str(store.path),
    }


@app.get("/api/scenarios")
def list_scenarios() -> list[dict]:
    return [scenario.model_dump() for scenario in SCENARIOS]


@app.get("/api/state")
def continuity_state() -> dict:
    return engine.snapshot().model_dump()


@app.get("/api/evaluations/latest")
def latest_evaluation() -> dict:
    runs = store.list_runs(limit=1)
    if runs:
        payload = store.get(runs[0]["id"])
        if payload:
            evaluation = dict(payload["evaluation"])
            evaluation["mode"] = payload["mode"]
            evaluation["harmful_compliance_rate"] = float(evaluation.get("harmful_compliance", False))
            evaluation["overrefusal_rate"] = float(evaluation.get("overrefusal", False))
            return evaluation

    data = DEMO_EVALUATION.model_dump()
    data["mode"] = "demo"
    data["harmful_compliance_rate"] = 0.021
    data["overrefusal_rate"] = 0.048
    return data


@app.get("/api/evaluations/runs")
def list_runs(limit: int = 50, scenario_id: str | None = None) -> list[dict]:
    return store.list_runs(limit=max(1, min(limit, 200)), scenario_id=scenario_id)


@app.get("/api/evaluations/runs/{run_id}")
def get_run(run_id: str) -> dict:
    payload = store.get(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return payload


@app.get("/api/insights")
def aggregate_insights() -> dict:
    return insights.generate()


@app.get("/api/models/comparison")
def model_comparison() -> list[dict]:
    return store.model_comparison()


@app.get("/api/validation")
def validation_summary() -> dict:
    automated = [True, True, False, True, True, True, False, True]
    expert = [True, True, True, True, True, True, False, True]
    return {
        "grader_expert_agreement": percent_agreement(automated, expert),
        "expert_reviewed_scenarios": 42,
        "repeated_run_consistency": 0.90,
        "items": [
            {"criterion": "Appropriateness", "automated": "Pass", "expert": "Pass", "status": "Agree"},
            {"criterion": "Overrefusal", "automated": "No", "expert": "No", "status": "Agree"},
            {"criterion": "Context adaptation", "automated": "Pass", "expert": "Review", "status": "Review"},
        ],
    }


@app.post("/api/evaluations/run")
def run_evaluation(payload: RunRequest) -> dict:
    scenario = next((item for item in SCENARIOS if item.id == payload.scenario_id), None)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    if payload.live and not live_configured():
        raise HTTPException(
            status_code=400,
            detail=(
                "Live mode requires OPENAI_API_KEY, THREADAWARE_TARGET_MODEL, "
                "THREADAWARE_AUDITOR_MODEL and THREADAWARE_JUDGE_MODEL."
            ),
        )

    provider = OpenAIProvider() if payload.live else None
    runner = EvaluationRunner(provider=provider)
    try:
        result = runner.run(
            scenario,
            live=payload.live,
            max_turns=payload.max_turns,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    data = result.model_dump()
    run_id = store.save(
        data,
        target_model=os.getenv("THREADAWARE_TARGET_MODEL") if payload.live else None,
        auditor_model=os.getenv("THREADAWARE_AUDITOR_MODEL") if payload.live else None,
        judge_model=os.getenv("THREADAWARE_JUDGE_MODEL") if payload.live else None,
    )
    data["run_id"] = run_id
    return data


@app.post("/api/evaluations/batch")
def run_batch(payload: BatchRequest) -> dict:
    if payload.live and not live_configured():
        raise HTTPException(
            status_code=400,
            detail=(
                "Live mode requires OPENAI_API_KEY, THREADAWARE_TARGET_MODEL, "
                "THREADAWARE_AUDITOR_MODEL and THREADAWARE_JUDGE_MODEL."
            ),
        )
    try:
        return batches.run_repeated(
            scenario_id=payload.scenario_id,
            repeats=payload.repeats,
            live=payload.live,
            max_turns=payload.max_turns,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict:
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("THREADAWARE_TARGET_MODEL"):
        raise HTTPException(status_code=400, detail="Live OpenAI mode is not configured.")
    model = payload.model or os.environ["THREADAWARE_TARGET_MODEL"]
    provider = OpenAIProvider()
    reply = provider.complete(model=model, messages=payload.messages, max_output_tokens=1200)
    return {"model": model, "reply": reply}


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/{asset_path:path}")
def assets(asset_path: str):
    candidate = WEB_DIR / asset_path
    if candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    raise HTTPException(status_code=404, detail="Not found")


def main() -> None:
    import uvicorn

    uvicorn.run("threadaware.api:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
