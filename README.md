# ThreadAware

ThreadAware is an open-source evaluation framework for studying how AI systems behave across long, evolving conversations where user needs, constraints, priorities, sensitivities, and conversational direction can change over time.

Its core question is not simply whether a model gives a good answer to one prompt. ThreadAware studies whether a model remains helpful, appropriate, context-aware, coherent, and safe throughout a long conversation as the conversation itself changes.

## Quick start

Requires Python 3.11+.

```bash
git clone https://github.com/FreezeGrover/ThreadAware
cd ThreadAware
python -m venv .venv
```

Activate the environment.

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install and launch:

```bash
pip install -e .
threadaware
```

ThreadAware starts the FastAPI backend and the frontend together, waits for the local server to become reachable, and then attempts to open the default browser automatically at:

```text
http://127.0.0.1:8000
```

If browser opening is unavailable, the URL is still printed clearly in the terminal. Press `Ctrl+C` to stop the server.

Optional convenience launchers are also included:

- Windows: `run_threadaware.bat`
- macOS/Linux: `./run_threadaware.sh`

The Python package entrypoint remains the primary supported method.

## Demo mode: no API key required

ThreadAware launches without an API key.

In demo mode:

- the full interface opens;
- the storyboard-based dashboard remains navigable;
- demo scenarios can run;
- synthetic/example transcripts are available;
- continuity, memory, interpretation, evaluation, validation, and Insights pages can be explored;
- live generative model calls are clearly treated as unavailable/demo-only;
- example evaluation values are labeled as demo data;
- expert-validation numbers are **not** fabricated or presented as real evidence.

This means a reviewer can inspect the project immediately after cloning it, without needing access to the author's ChatGPT account, a hosted service, or a paid deployment.

## Enabling live OpenAI mode

Copy `.env.example` to a local `.env` file in the repository root and add your own API key.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

Then edit `.env` locally.

```bash
OPENAI_API_KEY=

THREADAWARE_TARGET_MODEL=
THREADAWARE_AUDITOR_MODEL=
THREADAWARE_JUDGE_MODEL=
THREADAWARE_UNDERSTANDING_MODEL=
THREADAWARE_SCENARIO_MODEL=
THREADAWARE_INSIGHTS_MODEL=
THREADAWARE_FALLBACK_MODEL=

THREADAWARE_TOTAL_TOKEN_BUDGET=10000000
THREADAWARE_MAX_TOKENS_PER_RUN=20000
THREADAWARE_MAX_BATCH_RUNS=25
```

Model identifiers are configuration, not hard-coded research assumptions. Different models can be assigned independently to the target, simulated user/auditor, conversation-understanding layer, automated judge, scenario generation, and Insights analysis.

The API key stays server-side. Never place it in frontend JavaScript, screenshots, logs, saved evaluation payloads, test fixtures, or exported public research artifacts. `.env` is ignored by Git.

## Project-side 10M-token budget

ThreadAware supports a configured project budget ledger for an approximately 10,000,000-token API allocation.

```text
THREADAWARE_TOTAL_TOKEN_BUDGET=10000000
THREADAWARE_MAX_TOKENS_PER_RUN=20000
THREADAWARE_MAX_BATCH_RUNS=25
```

The configured total is a project-side safety ceiling. ThreadAware does **not** assume that the OpenAI API exposes the user's real remaining grant balance.

The architecture is designed to keep model roles separate so high-value reasoning can use stronger models while high-volume simpler work can use cheaper models where appropriate without changing the evaluation contract.

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
Conversation Continuity Engine
  ↓
Conversation Memory & Understanding
  ↓
Automated Judge
  ↓
Expert Validation
  ↓
Repeated Runs / Model Comparison
  ↓
Insights & Reproducible Results
```

The Continuity Engine is intentionally dialogue-level. It tracks evolving goals, constraints, preferences, decisions, unresolved questions, important updates, and sensitivity. The adaptive memory/interpretation layer is separate and handles evolving conversational understanding, topic shifts, returning topics, and materially plausible interpretations.

ThreadAware deliberately does not turn this into a rigid formal world-state or hard-coded pronoun/reference-resolution system.

## Conversational intelligence

The conversational layer is designed to distinguish:

- casual conversation;
- ThreadAware/project work;
- mixed casual/project conversation;
- returns to earlier conversational threads.

The live assistant is expected to remain warm, natural, perceptive, composed, and subtly expressive without forcing research terminology into ordinary conversation.

The interpretation layer can preserve multiple genuinely plausible readings and ask a concise clarification question when choosing the wrong interpretation would materially affect the answer.

Memory can update earlier related information rather than simply accumulating disconnected notes, while preserving useful provenance.

## Evaluation dimensions

ThreadAware includes explicit evaluation constructs for:

- helpfulness;
- appropriateness;
- balanced behavior;
- context adaptation;
- continuity;
- severity awareness;
- harmful compliance;
- unnecessary overrefusal;
- conversational awareness;
- clarification quality;
- memory-update quality;
- topic-shift awareness.

Automated evaluation remains conceptually separate from real expert validation.

## Repeated runs and model comparison

The repeated-run infrastructure supports:

```text
Scenario × Model × N repetitions
```

and can summarize variation across repeated evaluations rather than relying on one transcript.

Model comparison is intended to expose measured differences across dimensions and uncertainty, not a simplistic overall winner.

## Local data storage

Runtime data is stored outside the repository by default so local databases are not scattered into the source tree or accidentally committed.

Default application-data locations:

Windows:

```text
%LOCALAPPDATA%\ThreadAware
```

macOS:

```text
~/Library/Application Support/ThreadAware
```

Linux:

```text
$XDG_DATA_HOME/threadaware
```

or, when `XDG_DATA_HOME` is not set:

```text
~/.local/share/threadaware
```

Within that directory ThreadAware uses predictable locations for:

- SQLite evaluation runs: `threadaware_runs.sqlite3`;
- exports: `exports/`;
- local settings: `settings.json`;
- token-usage ledger: `token_usage.json`.

These can be overridden for controlled research environments with variables such as `THREADAWARE_DATA_DIR` and `THREADAWARE_DB_PATH`.

## API

Key endpoints include:

```text
GET  /api/health
GET  /api/scenarios
GET  /api/state
GET  /api/memory
GET  /api/evaluations/latest
GET  /api/evaluations/runs
GET  /api/evaluations/runs/{run_id}
GET  /api/validation
GET  /api/insights
GET  /api/models/comparison
POST /api/understanding
POST /api/evaluations/run
POST /api/evaluations/batch
POST /api/chat
```

A live evaluation follows the configured pipeline:

```text
Auditor → Target → Continuity → Understanding → Judge → Stored Result
```

## Reproducibility

ThreadAware is structured so evaluation runs can retain enough metadata to reproduce experiments, including scenario/model configuration, stored transcripts, evaluation outputs, and run IDs. The project is being extended toward fuller run manifests containing prompt/rubric versions, seeds where applicable, model parameters, ThreadAware version, and token usage.

Synthetic fixtures are used for public tests and examples. Private participant data, secrets, and sensitive raw conversations should not be committed.

## Research validity

ThreadAware treats automated graders as research instruments rather than ground truth. The architecture supports separate target and judge models, repeated runs, disagreement analysis, and later expert review.

Until real experts have reviewed transcripts, the Validation page explicitly reports that expert evidence is pending. Placeholder/demo statistics are not represented as empirical validation.

## Development preview vs final deliverable

A ChatGPT Sites preview may be used during development to visually inspect and refine the interface. It is **not** a dependency of ThreadAware.

The final reviewer experience is the normal open-source Python flow:

```bash
git clone https://github.com/FreezeGrover/ThreadAware
cd ThreadAware
python -m venv .venv
pip install -e .
threadaware
```

No ChatGPT account access, hosted ThreadAware server, Sites workspace permission, or paid deployment service is required to run the repository locally.
