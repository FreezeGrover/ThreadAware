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
Insights & Reproducible Results
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

The browser hydrates its scenario, continuity, evaluation, and validation data from the Python API rather than relying only on static mock values.

## API

ThreadAware exposes a FastAPI service with initial endpoints:

```text
GET  /api/health
GET  /api/scenarios
GET  /api/state
GET  /api/evaluations/latest
GET  /api/validation
POST /api/evaluations/run
POST /api/chat
```

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

The app works in demo mode without an API key. To enable live model calls, copy `.env.example` to `.env` and set the relevant values in your environment:

```bash
OPENAI_API_KEY=
THREADAWARE_TARGET_MODEL=
THREADAWARE_AUDITOR_MODEL=
THREADAWARE_JUDGE_MODEL=
THREADAWARE_MAX_TOKENS_PER_RUN=20000
```

Model identifiers are configuration, not hard-coded project assumptions, so the system can use whichever eligible models are covered by the project's available OpenAI API allocation.

Never commit API keys, secrets, private participant data, or sensitive transcripts.

## Current implementation status

Implemented:

- provider abstraction
- OpenAI provider adapter
- continuity state representation
- continuity engine
- multi-turn scenario library
- evaluation rubric structure
- deterministic pass/fail aggregation
- grader/expert agreement utility
- FastAPI backend
- frontend/backend integration
- demo and live-mode separation

Next implementation stages:

- auditor-driven multi-turn scenario execution
- automated judge output using structured scoring
- token-budget enforcement per evaluation run
- transcript persistence and reproducible run manifests
- repeated-run analysis
- expert-review import/export
- richer scenario realism and validity checks

## Open-source research outputs

Planned reproducible artifacts include scenario definitions, rubrics, scoring logic, evaluation code, public example transcripts, aggregate outputs, and methodology documentation.
