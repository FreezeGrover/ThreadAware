from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from threadaware.common.models import Turn
from threadaware.continuity.engine import ContinuityEngine
from threadaware.conversation.intelligence import ConversationalIntelligence
from threadaware.evaluations.batch import BatchRunner
from threadaware.evaluations.runner import EvaluationRunner
from threadaware.insights.analysis import InsightEngine
from threadaware.memory.understanding import ConversationUnderstandingEngine
from threadaware.paths import app_data_dir, database_path, exports_dir, settings_path
from threadaware.providers.openai_provider import OpenAIProvider
from threadaware.scenarios.library import SCENARIOS
from threadaware.storage.runs import RunStore


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
load_dotenv(ROOT / ".env", override=False)

app = FastAPI(title="ThreadAware API", version="0.6.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ContinuityEngine()

store = RunStore()
insights = InsightEngine(store=store)
batches = BatchRunner(store=store)
understanding = ConversationUnderstandingEngine()
conversation = ConversationalIntelligence()

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


def model_config() -> dict[str, str | None]:
    return {
        "target": os.getenv("THREADAWARE_TARGET_MODEL"),
        "auditor": os.getenv("THREADAWARE_AUDITOR_MODEL"),
        "judge": os.getenv("THREADAWARE_JUDGE_MODEL"),
        "understanding": os.getenv("THREADAWARE_UNDERSTANDING_MODEL"),
        "scenario": os.getenv("THREADAWARE_SCENARIO_MODEL"),
        "insights": os.getenv("THREADAWARE_INSIGHTS_MODEL"),
        "fallback": os.getenv("THREADAWARE_FALLBACK_MODEL"),
    }


def live_configured() -> bool:
    models = model_config()
    return bool(
        os.getenv("OPENAI_API_KEY")
        and models["target"]
        and models["auditor"]
        and models["judge"]
        and models["understanding"]
    )


def chat_live_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") and os.getenv("THREADAWARE_TARGET_MODEL"))


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ready",
        "mode": "live" if live_configured() else "demo",
        "chat_mode": "live" if chat_live_configured() else "demo",
        "provider": "openai" if chat_live_configured() else None,
        "pipeline": "auditor-target-continuity-understanding-judge",
        "conversation_understanding": "interpretations-memory-topic-shifts",
        "conversational_intelligence": "casual-project-mixed-routing",
        "storage": str(store.path),
        "data_directory": str(app_data_dir()),
        "exports_directory": str(exports_dir()),
        "settings_path": str(settings_path()),
        "token_budget": int(os.getenv("THREADAWARE_TOTAL_TOKEN_BUDGET", "10000000")),
        "models": model_config(),
    }


@app.get("/api/scenarios")
def list_scenarios() -> list[dict]:
    return [scenario.model_dump() for scenario in SCENARIOS]


@app.get("/api/state")
def continuity_state() -> dict:
    return engine.snapshot().model_dump()


@app.get("/api/memory")
def memory_state() -> dict:
    return {
        "active_topic": understanding.active_topic,
        "items": [item.model_dump() for item in understanding.memory.snapshot()],
    }


@app.post("/api/understanding")
def analyze_conversation(payload: ChatRequest) -> dict:
    if not payload.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    understanding_model = os.getenv("THREADAWARE_UNDERSTANDING_MODEL")
    live = bool(os.getenv("OPENAI_API_KEY") and understanding_model)
    if live:
        understanding.provider = OpenAIProvider()
        understanding.model = understanding_model

    result = understanding.analyze(turns=payload.messages, live=live)
    return result.model_dump()


@app.get("/api/evaluations/latest")
def latest_evaluation() -> dict:
    runs = store.list_runs(limit=1)
    if runs:
        payload = store.get(runs[0]["id"])
        if payload and payload.get("mode") == "live":
            evaluation = dict(payload["evaluation"])
            evaluation["mode"] = payload["mode"]
            evaluation["available"] = True
            evaluation["harmful_compliance_rate"] = float(evaluation.get("harmful_compliance", False))
            evaluation["overrefusal_rate"] = float(evaluation.get("overrefusal", False))
            return evaluation

    return {
        "mode": "demo",
        "demo_only": True,
        "available": False,
        "message": "Run a scenario to generate an explicitly labelled demonstration result.",
    }


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
    """Expose validation architecture without presenting synthetic values as evidence."""
    return {
        "source": "demo-placeholder",
        "has_real_expert_evidence": False,
        "grader_expert_agreement": None,
        "expert_reviewed_scenarios": 0,
        "repeated_run_consistency": None,
        "status": "awaiting-expert-evidence",
        "items": [],
        "note": "Expert-review workflow is available, but no synthetic agreement values are presented as real validation evidence.",
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
                "Live evaluation requires OPENAI_API_KEY plus target, auditor, judge, "
                "and understanding model configuration."
            ),
        )

    provider = OpenAIProvider() if payload.live else None
    runner = EvaluationRunner(provider=provider)
    try:
        result = runner.run(scenario, live=payload.live, max_turns=payload.max_turns)
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
        raise HTTPException(status_code=400, detail="Live evaluation model roles are not fully configured.")
    configured_max = max(1, int(os.getenv("THREADAWARE_MAX_BATCH_RUNS", "25")))
    if payload.repeats > configured_max:
        raise HTTPException(status_code=400, detail=f"Batch size exceeds THREADAWARE_MAX_BATCH_RUNS={configured_max}.")
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
    if not payload.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    intent = conversation.classify(payload.messages)
    live = chat_live_configured()

    if not live:
        interpretation = understanding.analyze(turns=payload.messages, live=False)
        if interpretation.interpretation.clarification_needed:
            reply = interpretation.interpretation.clarification_question
        else:
            reply = conversation.demo_reply(payload.messages, intent)
        return {
            "model": None,
            "mode": "demo",
            "demo_only": True,
            "reply": reply,
            "clarification_needed": interpretation.interpretation.clarification_needed,
            "conversation_mode": intent.mode,
            "intent_reason": intent.reason,
            "understanding": interpretation.model_dump(),
        }

    provider = OpenAIProvider()
    model = payload.model or os.environ["THREADAWARE_TARGET_MODEL"]
    understanding.provider = provider
    understanding.model = os.getenv("THREADAWARE_UNDERSTANDING_MODEL") or model

    interpretation = understanding.analyze(turns=payload.messages, live=True)

    if interpretation.interpretation.clarification_needed:
        return {
            "model": model,
            "mode": "live",
            "reply": interpretation.interpretation.clarification_question,
            "clarification_needed": True,
            "conversation_mode": intent.mode,
            "understanding": interpretation.model_dump(),
        }

    memory_context = [item.model_dump() for item in understanding.memory.active()]
    system_parts = [
        conversation.system_guidance(intent),
        "Use the full conversation and relevant conversation memory. Do not invent missing facts.",
        "If later information updates an earlier topic, prefer the newer information while preserving still-relevant earlier context.",
    ]
    if interpretation.topic_shift.shifted and interpretation.topic_shift.acknowledgement:
        system_parts.append(
            "The user has meaningfully shifted or returned to a topic. Naturally acknowledge this awareness in one brief sentence when useful: "
            + interpretation.topic_shift.acknowledgement
        )
    system_parts.append(f"Relevant conversation memory: {memory_context}")

    reply = provider.complete(
        model=model,
        messages=[Turn(role="system", content="\n".join(system_parts)), *payload.messages],
        max_output_tokens=1200,
        role="target",
    )
    return {
        "model": model,
        "mode": "live",
        "reply": reply,
        "clarification_needed": False,
        "conversation_mode": intent.mode,
        "intent_reason": intent.reason,
        "understanding": interpretation.model_dump(),
    }


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
    # Backward-compatible programmatic entrypoint; the package console script points
    # directly at threadaware.launcher:main.
    from threadaware.launcher import main as launch

    launch()


if __name__ == "__main__":
    main()
