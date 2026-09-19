from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from threadaware.paths import database_path


DEFAULT_DB_PATH = database_path()


class RunStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else DEFAULT_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    target_model TEXT,
                    auditor_model TEXT,
                    judge_model TEXT,
                    passed INTEGER NOT NULL,
                    helpfulness REAL NOT NULL,
                    appropriateness REAL NOT NULL,
                    balanced_behavior REAL NOT NULL,
                    context_adaptation REAL NOT NULL,
                    continuity REAL NOT NULL,
                    severity_awareness REAL NOT NULL,
                    harmful_compliance INTEGER NOT NULL,
                    overrefusal INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def save(
        self,
        payload: dict[str, Any],
        *,
        target_model: str | None = None,
        auditor_model: str | None = None,
        judge_model: str | None = None,
    ) -> str:
        run_id = str(uuid4())
        evaluation = payload["evaluation"]
        scenario = payload["scenario"]
        created_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    id, created_at, scenario_id, mode,
                    target_model, auditor_model, judge_model,
                    passed, helpfulness, appropriateness, balanced_behavior,
                    context_adaptation, continuity, severity_awareness,
                    harmful_compliance, overrefusal, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    created_at,
                    scenario["id"],
                    payload["mode"],
                    target_model,
                    auditor_model,
                    judge_model,
                    int(bool(evaluation["passed"])),
                    float(evaluation["helpfulness"]),
                    float(evaluation["appropriateness"]),
                    float(evaluation["balanced_behavior"]),
                    float(evaluation["context_adaptation"]),
                    float(evaluation["continuity"]),
                    float(evaluation["severity_awareness"]),
                    int(bool(evaluation.get("harmful_compliance", False))),
                    int(bool(evaluation.get("overrefusal", False))),
                    json.dumps(payload),
                ),
            )
        return run_id

    def list_runs(self, *, limit: int = 50, scenario_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM runs"
        params: list[Any] = []
        if scenario_id:
            sql += " WHERE scenario_id = ?"
            params.append(scenario_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM runs WHERE id = ?", (run_id,)).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_runs,
                    AVG(helpfulness) AS helpfulness,
                    AVG(appropriateness) AS appropriateness,
                    AVG(balanced_behavior) AS balanced_behavior,
                    AVG(context_adaptation) AS context_adaptation,
                    AVG(continuity) AS continuity,
                    AVG(severity_awareness) AS severity_awareness,
                    AVG(passed) AS pass_rate,
                    AVG(harmful_compliance) AS harmful_compliance_rate,
                    AVG(overrefusal) AS overrefusal_rate
                FROM runs
                """
            ).fetchone()
        return {key: row[key] for key in row.keys()}

    def model_comparison(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(target_model, 'demo') AS model,
                    COUNT(*) AS runs,
                    AVG(helpfulness) AS helpfulness,
                    AVG(appropriateness) AS appropriateness,
                    AVG(context_adaptation) AS context_adaptation,
                    AVG(continuity) AS continuity,
                    AVG(passed) AS pass_rate,
                    AVG(harmful_compliance) AS harmful_compliance_rate,
                    AVG(overrefusal) AS overrefusal_rate
                FROM runs
                GROUP BY COALESCE(target_model, 'demo')
                ORDER BY runs DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]
