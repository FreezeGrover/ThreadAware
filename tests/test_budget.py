from pathlib import Path

import pytest

from threadaware.budget import TokenBudgetExceeded, TokenLedger


def test_token_ledger_tracks_role_model_and_remaining_budget(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("THREADAWARE_TOTAL_TOKEN_BUDGET", "1000")
    ledger = TokenLedger(tmp_path / "usage.json")

    state = ledger.record(
        role="judge",
        model="test-model",
        input_tokens=120,
        output_tokens=80,
        total_tokens=200,
    )

    assert state["total_tokens"] == 200
    assert state["remaining_configured_budget"] == 800
    assert state["by_role"]["judge"]["total_tokens"] == 200
    assert state["by_model"]["test-model"]["total_tokens"] == 200


def test_token_ledger_blocks_calls_that_exceed_remaining_budget(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("THREADAWARE_TOTAL_TOKEN_BUDGET", "100")
    ledger = TokenLedger(tmp_path / "usage.json")
    ledger.record(role="target", model="test-model", input_tokens=50, output_tokens=40, total_tokens=90)

    with pytest.raises(TokenBudgetExceeded):
        ledger.ensure_available(20)
