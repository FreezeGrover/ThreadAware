# ThreadAware

ThreadAware is an open-source evaluation framework for studying how AI systems behave across long, evolving conversations where user needs, constraints, priorities, and risk can change over time.

The core focus is **conversation continuity**: whether a model continues to respond appropriately as goals, constraints, preferences, decisions, unresolved questions, and sensitivity evolve across many turns.

## Architecture

```text
Scenario
  ↓
Simulated User / Auditor
  ↓
Target Model
  ↓
Long Multi-turn Conversation
  ↓
Continuity Engine
  ↓
Automated Evaluator / Judge
  ↓
Expert Validation
  ↓
Persistent Runs, Model Comparison & Insights
```

The Continuity Engine is intentionally dialogue-level. It does not depend on formal reference tracking, ambiguity resolution, or world-state modelling.

## Evaluation dimensions

ThreadAware is structured around explicit evaluation constructs including:

- helpfulness
- appropriateness
- balanced behavior
- harmful compliance
- unnecessary overrefusal
- context adaptation
- continuity
- severity awareness
- grader ↔ expert agreement
- repeated-run consistency

Each construct can be paired with explicit definitions, scoring rules, and pass/fail criteria.

## Web interface

A first-pass UI lives in `web/` and includes:

- Chat
- Continuity
- Scenarios
- Evaluations
- Validation
- Insights

The browser hydrates continuity and evaluation data from the Python API. The dashboard is intentionally a first-pass product shell so it can be refined without changing the evaluation architecture.

## API

ThreadAware exposes a FastAPI service with endpoints including:

```text
GET  /api/health
GET  /api/scenarios
GET  /api/state
GET  /api/evaluations/latest
GET  /api/evaluations/runs
GET  /api/evaluations/runs/{run_id}
GET  /api/validation
GET  /api/insights
GET  /api/models/comparison
POST /api/evaluations/run
POST /api/evaluations/batch
POST /api/chat
```

### Single evaluation

`POST /api/evaluations/run` executes:

```text
Auditor → Target → Continuity → Judge → Stored Result
```

The response contains the full transcript, continuity state, judge details, evaluation scores, and a persistent run ID.

### Repeated-run evaluation

`POST /api/evaluations/batch` runs the same scenario multiple times and reports mean, standard deviation, minimum, maximum, and pass rate for the core evaluation dimensions. This supports stability analysis rather than drawing conclusions from a single transcript.

### Persistent research runs

Evaluation runs are stored in SQLite by default (`threadaware_runs.sqlite3`). Set `THREADAWARE_DB_PATH` to choose another location.

Stored data supports:

- run history
- transcript retrieval
- aggregate evaluation scores
- repeated-run analysis
- model-to-model comparison
- harmful-compliance and overrefusal rates
- research-oriented Insights summaries

## Running locally

Requires Python 3.11+.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install:

```bash
pip install -e .
```

Start ThreadAware:

```bash
threadaware
```

Then open:

```text
http://127.0.0.1:8000
```

## OpenAI live mode

The app works in deterministic demo mode without an API key. To enable live model calls, copy `.env.example` to `.env` and configure:

```bash
OPENAI_API_KEY=
THREADAWARE_TARGET_MODEL=
THREADAWARE_AUDITOR_MODEL=
THREADAWARE_JUDGE_MODEL=
THREADAWARE_MAX_TOKENS_PER_RUN=20000
```

Model identifiers are configuration, not hard-coded project assumptions, so the system can use whichever eligible models are covered by the project's OpenAI API allocation.

Never commit API keys, secrets, private participant data, or sensitive transcripts.

## Current implementation status

Implemented:

- provider abstraction and OpenAI adapter
- dialogue-level Continuity Engine
- scenario library
- auditor-driven multi-turn execution
- target model interaction
- automated judge scoring
- explicit evaluation rubrics and pass/fail aggregation
- harmful-compliance and overrefusal flags
- grader/expert agreement utility
- persistent SQLite run storage
- repeated-run batch evaluation and stability statistics
- model comparison summaries
- aggregate Insight Engine
- FastAPI backend
- first-pass dashboard and frontend/backend integration
- demo/live separation
- unit and API-oriented tests

Important next research stages:

- real expert-review import/export workflows
- empirical grader validation with subject-matter experts
- larger scenario suites and more varied conversation lengths
- scenario realism and eval-awareness checks
- stronger token-budget accounting and cost telemetry
- reproducible dataset/run manifest export
- multilingual and regional scenario coverage where appropriate
- dashboard refinement and research UX improvements

## Open-source research outputs

The intended reproducible artifacts include scenario definitions, rubrics, scoring logic, evaluation code, public example transcripts, aggregate outputs, validation methodology, and documentation sufficient for third-party reproduction.
