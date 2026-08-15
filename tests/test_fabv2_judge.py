import importlib.util
from pathlib import Path


def _judge_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "benchmarks"
        / "fabv2"
        / "evals"
        / "frozen"
        / "judge.py"
    )
    spec = importlib.util.spec_from_file_location("fabv2_frozen_judge", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fabv2_judge_separates_optimization_signal_from_dealbreaker_score():
    judge = _judge_module()
    verdict = judge.score_question(
        "q004",
        "CRWD CAGR was 32.82%, while the other requested calculations are unavailable.",
    )

    assert verdict["partial_credit"] == 0.0
    assert verdict["ungated_credit"] > 0.0
    assert verdict["numeric_criterion_recall"] == 1 / 3
    assert verdict["rubric_numeric_coverage"] == 3 / 4


def test_rubric_numeric_coverage_is_answer_independent():
    judge = _judge_module()
    empty = judge.score_question("q004", "")
    correct_one = judge.score_question("q004", "32.82%")

    assert empty["rubric_numeric_coverage"] == correct_one["rubric_numeric_coverage"]
    assert empty["numeric_criterion_recall"] < correct_one["numeric_criterion_recall"]
