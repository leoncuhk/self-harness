"""Deterministic examples for uncertainty-aware candidate promotion."""

from dataclasses import replace
from pathlib import Path

import pytest

from self_harness.contracts import GoalContract
from self_harness.core import CaseOutcome, SplitResult, load_experiment, run_experiment
from self_harness.gate import decide
from self_harness.measurement import (
    MeasurementContract,
    load_measurement_contract,
    matched_question_estimate,
)

ROOT = Path(__file__).resolve().parents[1]


def split_result(label: str, values: list[float], *, metric: str = "quality") -> SplitResult:
    outcomes = tuple(
        CaseOutcome(
            case_id=f"q{index:03d}",
            split="holdout",
            stratum="demo",
            status="passed",
            score=value,
            duration_s=1.0,
            metrics={metric: value},
        )
        for index, value in enumerate(values)
    )
    return SplitResult(
        split="holdout",
        variant=label,
        model="fixed-model",
        passed=len(outcomes),
        total=len(outcomes),
        score=sum(values),
        returncode=0,
        run_dir=".",
        outcomes=outcomes,
        metrics={metric: sum(values) / len(values)},
    )


def contract() -> MeasurementContract:
    return MeasurementContract(
        enabled=True,
        confidence=0.95,
        bootstrap_samples=2_000,
        minimum_pairs=4,
        seed=7,
    )


def test_measurement_contract_rejects_typos():
    with pytest.raises(ValueError, match="unknown measurement settings"):
        load_measurement_contract({"confidnce": 0.95})


def test_matched_estimate_accepts_consistent_question_level_gain():
    current = split_result("current", [0.3] * 8)
    candidate = split_result("candidate", [0.5] * 8)

    estimate = matched_question_estimate(
        current=current,
        candidate=candidate,
        metric="quality",
        direction="maximize",
        effect_floor=0.05,
        contract=contract(),
        familywise_comparisons=6,
    )

    assert estimate.pairs == 8
    assert estimate.mean_delta == pytest.approx(0.2)
    assert estimate.ci_low == pytest.approx(0.2)
    assert estimate.supports_improvement
    assert estimate.minimum_detectable_effect == pytest.approx(0.05)


def test_matched_estimate_rejects_positive_mean_with_unresolved_regression_risk():
    current = split_result("current", [0.5] * 8)
    candidate = split_result("candidate", [1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.4])

    estimate = matched_question_estimate(
        current=current,
        candidate=candidate,
        metric="quality",
        direction="maximize",
        effect_floor=0.0,
        contract=contract(),
        familywise_comparisons=6,
    )

    assert estimate.mean_delta > 0
    assert estimate.ci_low < 0
    assert not estimate.supports_non_degradation
    assert not estimate.supports_improvement


def test_objective_gate_can_require_matched_uncertainty_evidence():
    current_train = split_result("current", [0.2] * 8)
    candidate_train = split_result("candidate", [0.4] * 8)
    current_holdout = split_result("current", [0.3] * 8)
    candidate_holdout = split_result("candidate", [0.5] * 8)

    decision = decide(
        gate="objective",
        goal=GoalContract(
            primary_metric="quality",
            min_delta=0.05,
            require_holdout_improvement=True,
        ),
        measurement=contract(),
        familywise_comparisons=6,
        current_train=current_train,
        current_holdout=current_holdout,
        candidate_train=candidate_train,
        candidate_holdout=candidate_holdout,
    )

    assert decision.accepted
    assert decision.train_estimate is not None
    assert decision.holdout_estimate is not None
    assert decision.to_dict()["holdout_estimate"]["supports_improvement"] is True
    assert "matched CI" in decision.reason


def test_missing_question_invalidates_matched_promotion_matrix():
    current = split_result("current", [0.2] * 8)
    candidate = split_result("candidate", [0.5] * 8)
    candidate = replace(
        candidate,
        outcomes=(replace(candidate.outcomes[0], status="apparatus"), *candidate.outcomes[1:]),
    )

    estimate = matched_question_estimate(
        current=current,
        candidate=candidate,
        metric="quality",
        direction="maximize",
        effect_floor=0.05,
        contract=contract(),
    )

    assert estimate.pairs == 7
    assert estimate.missing_candidate == ("q000",)
    assert not estimate.complete_pairs
    assert not estimate.supports_improvement


def test_measurement_contract_is_publication_opt_in():
    smoke = load_experiment(ROOT / "configs" / "fabv2_evolve_smoke.toml")
    replicated = load_experiment(ROOT / "configs" / "fabv2_evolve_replicated.toml")

    assert not smoke.measurement.enabled
    assert replicated.measurement.enabled
    assert replicated.measurement.minimum_pairs == 4


def test_runtime_cannot_expand_pre_registered_candidate_family(tmp_path: Path):
    experiment = load_experiment(ROOT / "configs" / "coding_demo.toml")

    with pytest.raises(ValueError, match="cannot exceed the frozen experiment contract"):
        run_experiment(
            experiment,
            output_dir=tmp_path / "run",
            max_iterations=experiment.max_iterations + 1,
        )
