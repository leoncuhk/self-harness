from __future__ import annotations

import pytest

from self_harness.contracts import GoalContract, MetricConstraint, load_goal_contract


def test_goal_contract_normalizes_improvement_direction():
    assert GoalContract(direction="maximize").improvement(2.0, 3.5) == 1.5
    assert GoalContract(direction="minimize").improvement(3.5, 2.0) == 1.5


def test_goal_contract_applies_effect_floor():
    goal = GoalContract(min_delta=0.1)
    assert goal.improved(1.0, 1.11)
    assert not goal.improved(1.0, 1.1)
    assert goal.non_degrading(1.0, 1.0)


def test_metric_constraint_rejects_missing_and_inverted_bounds():
    with pytest.raises(ValueError, match="needs minimum"):
        MetricConstraint(metric="quality")
    with pytest.raises(ValueError, match="minimum above maximum"):
        MetricConstraint(metric="quality", minimum=2.0, maximum=1.0)


def test_load_goal_contract_reads_constraints():
    goal = load_goal_contract(
        {
            "primary_metric": "partial_credit",
            "direction": "maximize",
            "min_delta": 0.01,
            "require_holdout_improvement": True,
            "constraints": [{"metric": "correctness", "minimum": 0.5}],
        }
    )
    assert goal.primary_metric == "partial_credit"
    assert goal.require_holdout_improvement
    assert goal.constraints[0].accepts(0.5)
    assert not goal.constraints[0].accepts(None)


def test_goal_contract_rejects_unknown_direction():
    with pytest.raises(ValueError, match="invalid goal direction"):
        GoalContract(direction="sideways")
