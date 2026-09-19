from threadaware.evaluations.runner import EvaluationRunner
from threadaware.scenarios.library import SCENARIOS


def test_demo_runner_returns_multi_turn_result():
    runner = EvaluationRunner()
    result = runner.run(SCENARIOS[0], live=False, max_turns=8)

    assert result.mode == "demo"
    assert len(result.transcript) >= 4
    assert result.evaluation.passed is True
    assert result.continuity.active_goals
    assert result.judge_details["source"] == "deterministic-demo"


def test_demo_runner_tracks_context_change():
    runner = EvaluationRunner()
    result = runner.run(SCENARIOS[0], live=False, max_turns=8)

    assert any("deadline moved" in item.lower() for item in result.continuity.updates)
    assert result.evaluation.context_adaptation >= 0.9
