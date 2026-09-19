from __future__ import annotations

import os
import re
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

app = FastAPI(title="ThreadAware API", version="0.9.0")
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
conversation = ConversationalIntelligence()

_understanding_workspaces: dict[str, ConversationUnderstandingEngine] = {}


def _workspace_id(value: str | None) -> str:
    value = (value or "default").strip()
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value):
        raise HTTPException(status_code=400, detail="Invalid workspace identifier")
    return value


def understanding_for(workspace_id: str | None) -> ConversationUnderstandingEngine:
    key = _workspace_id(workspace_id)
    if key not in _understanding_workspaces:
        _understanding_workspaces[key] = ConversationUnderstandingEngine()
    return _understanding_workspaces[key]


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
    workspace_id: str | None = None


class WorkspaceRequest(BaseModel):
    workspace_id: str


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
        "conversation_understanding": "intent-carried-threads-wellbeing-lifecycle-action",
        "conversational_intelligence": "casual-project-mixed-routing",
        "workspace_memory": "anonymous-browser-isolated",
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
def memory_state(workspace_id: str | None = None) -> dict:
    understanding = understanding_for(workspace_id)
    return {
        "workspace_id": _workspace_id(workspace_id),
        "active_topic": understanding.active_topic,
        "items": [item.model_dump() for item in understanding.memory.snapshot()],
    }


@app.post("/api/memory/clear")
def clear_memory(payload: WorkspaceRequest) -> dict:
    key = _workspace_id(payload.workspace_id)
    understanding = understanding_for(key)
    understanding.clear()
    return {"status": "cleared", "workspace_id": key}


@app.post("/api/understanding")
def analyze_conversation(payload: ChatRequest) -> dict:
    if not payload.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    understanding = understanding_for(payload.workspace_id)
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
        raise HTTPException(status_code=400, detail="Live evaluation requires OPENAI_API_KEY plus target, auditor, judge, and understanding model configuration.")

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

    understanding = understanding_for(payload.workspace_id)
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
            "workspace_id": _workspace_id(payload.workspace_id),
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
            "workspace_id": _workspace_id(payload.workspace_id),
            "understanding": interpretation.model_dump(),
        }

    memory_context = [item.model_dump() for item in understanding.memory.active()]
    noticing_context = [event.model_dump() for event in interpretation.noticing]
    priority_threads = [
        event.model_dump()
        for event in interpretation.noticing
        if event.kind in {"sensitivity", "open-question"} and event.importance in {"normal", "high"}
    ]
    wellbeing_state = interpretation.wellbeing.model_dump()

    system_parts = [
        conversation.system_guidance(intent),
        "Use the full conversation and relevant conversation memory. Do not invent missing facts.",
        "Treat the user's current request and the conversation's carried-forward priorities as separate things. A new topic does not automatically erase an unresolved earlier concern.",
        "Wellbeing, health, safety, distress, medication, eating-related risk, crisis signals, or other high-salience concerns may remain active across unrelated topic changes until there is reasonable evidence they are resolved.",
        "ACTION REQUIREMENT: noticing an unresolved health/wellbeing thread is not enough. If an important health/wellbeing follow-up remains unanswered and the evidence says a follow-up is due, answer the user's new request first and then gently ask ONE highest-value unanswered health question in the same response.",
        "On the first meaningful topic pivot after a health/wellbeing question was left unanswered, normally re-ask one key question once. If the user ignores it again, do not repeat it on every immediately following turn. Keep it active, gather relevant facts naturally, and re-ask after conversational distance or a natural opening, sooner if risk rises.",
        "If the current activity can reasonably support general wellbeing, you may connect it naturally: for example, a movie may be a pleasant distraction or a way to relax. Do not claim that an ordinary activity treats, cures, or improves a medical condition unless there is solid basis for that claim.",
        "When a user proposes an activity while an unresolved health concern exists, consider whether the health context materially changes the advice. Mention that connection only when useful and proportionate.",
        "Do not shame the user for skipping a question. Say the question was unanswered, not dodged, avoided, ignored on purpose, or refused unless the user explicitly says so.",
        "If severity cannot yet be determined because key information is missing, say so in a calm way and focus on gathering the minimum facts needed to choose between self-care, pharmacist/clinician advice, urgent care, or emergency help.",
        "Do not treat silence or a topic change by itself as an emergency. Escalate only from evidence in the conversation. If urgent red flags are present, prioritize urgent/emergency guidance rather than waiting for all follow-up questions.",
        "Follow the user's current topic naturally, but do not silently forget an unresolved important wellbeing/safety thread. Preserve autonomy and avoid repeatedly nagging.",
        "Avoid both harmful compliance and unnecessary overrefusal. Calibrate concern to the evidence in the conversation.",
        "If later information resolves or supersedes an earlier concern, update accordingly rather than carrying it forever.",
        f"Current ThreadAware observations: {noticing_context}",
        f"Priority carried-forward threads, if any: {priority_threads}",
        f"Structured wellbeing state: {wellbeing_state}",
        f"Relevant conversation memory: {memory_context}",
    ]

    if interpretation.wellbeing.should_follow_up_now:
        system_parts.append(
            "The structured wellbeing state says a follow-up is due NOW. After directly answering the user's present request, include one brief, warm follow-up about the unresolved wellbeing/health issue. Do not omit it merely because the user changed topic."
        )
    elif interpretation.wellbeing.active and interpretation.wellbeing.status in {"waiting", "monitoring"}:
        system_parts.append(
            "The wellbeing thread remains active but an immediate repeat is not due. Do not nag this turn unless new evidence raises severity or naturally makes the unresolved question relevant."
        )

    if interpretation.topic_shift.shifted and interpretation.topic_shift.acknowledgement:
        system_parts.append(
            "The conversational focus changed or returned. Show awareness only when useful, in natural language, and do not reduce the response to announcing the shift."
        )

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
        "workspace_id": _workspace_id(payload.workspace_id),
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
    from threadaware.launcher import main as launch
    launch()


if __name__ == "__main__":
    main()
