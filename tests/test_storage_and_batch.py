from pathlib import Path

from threadaware.evaluations.batch import BatchRunner
from threadaware.storage.runs import RunStore


def test_run_store_and_batch(tmp_path: Path):
    store = RunStore(tmp_path / "runs.sqlite3")
    batch = BatchRunner(store=store)

    result = batch.run_repeated(
        scenario_id="stress-goal-shift-001",
        repeats=3,
        live=False,
        max_turns=8,
    )

    assert result["repeats"] == 3
    assert len(result["run_ids"]) == 3
    assert result["pass_rate"] == 1.0

    rows = store.list_runs(limit=10)
    assert len(rows) == 3

    summary = store.summary()
    assert summary["total_runs"] == 3
    assert summary["context_adaptation"] > 0.9

    comparison = store.model_comparison()
    assert comparison[0]["model"] == "demo"
    assert comparison[0]["runs"] == 3
