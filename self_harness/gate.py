"""Promotion gates (P0-2).

Upstream self-harness promotes a candidate when the *combined* train + holdout
pass count improves::

    accepted = (train.passed + holdout.passed) > (current_train.passed + current_holdout.passed)

A sum lets a candidate rob Peter to pay Paul: holdout -2 and train +3 nets +1 and
is promoted, which is the textbook shape of overfitting to the split the proposer
can see.

The ``conservative`` gate replaces it with the Self-Harness promotion rule
(arXiv:2606.09498)::

    Δ_in >= 0  and  Δ_ho >= 0  and  max(Δ_in, Δ_ho) > 0

Neither split may regress, and at least one must improve, so no-op edits are
rejected too. ``combined`` is kept for A/B comparison against upstream behaviour.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, cast

from self_harness.measurement import MatchedEstimate, MeasurementContract, matched_question_estimate

if TYPE_CHECKING:  # pragma: no cover - typing only
    from self_harness.contracts import GoalContract
    from self_harness.core import SplitResult

VALID_GATES = ("conservative", "combined", "objective")


@dataclass(frozen=True)
class GateDecision:
    """One promotion decision with the deltas that produced it."""

    gate: str
    accepted: bool
    reason: str
    delta_in: int
    delta_ho: int
    delta_in_rate: float
    delta_ho_rate: float
    delta_in_score: float = 0.0
    delta_ho_score: float = 0.0
    train_estimate: MatchedEstimate | None = None
    holdout_estimate: MatchedEstimate | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the decision."""
        payload = asdict(self)
        payload["train_estimate"] = (
            None if self.train_estimate is None else self.train_estimate.to_dict()
        )
        payload["holdout_estimate"] = (
            None if self.holdout_estimate is None else self.holdout_estimate.to_dict()
        )
        return payload


def _deltas(current: SplitResult, candidate: SplitResult) -> tuple[int, float]:
    return (
        candidate.passed - current.passed,
        candidate.correctness - current.correctness,
    )


def decide(  # noqa: PLR0913 - the gate compares two splits before and after one edit
    *,
    gate: str,
    current_train: SplitResult,
    current_holdout: SplitResult,
    candidate_train: SplitResult,
    candidate_holdout: SplitResult,
    goal: GoalContract | None = None,
    measurement: MeasurementContract | None = None,
    familywise_comparisons: int = 1,
) -> GateDecision:
    """Return the promotion decision for one candidate."""
    if gate not in VALID_GATES:
        msg = f"invalid gate {gate!r}; expected one of {VALID_GATES}"
        raise ValueError(msg)

    delta_in, delta_in_rate = _deltas(current_train, candidate_train)
    delta_ho, delta_ho_rate = _deltas(current_holdout, candidate_holdout)
    delta_in_score = candidate_train.score - current_train.score
    delta_ho_score = candidate_holdout.score - current_holdout.score

    # An evaluation that mostly failed to run cannot promote anything. Apparatus
    # failures are excluded from the denominator, which is right for the estimate
    # and dangerous for the comparison: a candidate whose evaluation collapsed
    # would be scored on whichever handful of cases happened to complete, and a
    # small favourable sample clears a gate that a full evaluation would not.
    unmeasured = [
        f"{name} apparatus {result.apparatus}/{result.apparatus + result.total}"
        for name, result in (("train", candidate_train), ("holdout", candidate_holdout))
        if not result.measurable
    ]
    if unmeasured:
        return GateDecision(
            gate=gate,
            accepted=False,
            reason=f"unmeasured evaluation, no promotion: {'; '.join(unmeasured)}",
            delta_in=delta_in,
            delta_ho=delta_ho,
            delta_in_rate=delta_in_rate,
            delta_ho_rate=delta_ho_rate,
            delta_in_score=delta_in_score,
            delta_ho_score=delta_ho_score,
        )

    train_estimate: MatchedEstimate | None = None
    holdout_estimate: MatchedEstimate | None = None
    if gate == "objective":
        if goal is None:
            msg = "objective gate requires a goal contract"
            raise ValueError(msg)
        current_in = current_train.metric(goal.primary_metric)
        current_ho = current_holdout.metric(goal.primary_metric)
        candidate_in = candidate_train.metric(goal.primary_metric)
        candidate_ho = candidate_holdout.metric(goal.primary_metric)
        if None in (current_in, current_ho, candidate_in, candidate_ho):
            accepted = False
            reason = f"objective gate: metric {goal.primary_metric!r} was not measured"
        else:
            current_in = cast("float", current_in)
            current_ho = cast("float", current_ho)
            candidate_in = cast("float", candidate_in)
            candidate_ho = cast("float", candidate_ho)
            delta_in_score = goal.improvement(current_in, candidate_in)
            delta_ho_score = goal.improvement(current_ho, candidate_ho)
            constraints_ok = all(
                constraint.accepts(candidate_train.metric(constraint.metric))
                and constraint.accepts(candidate_holdout.metric(constraint.metric))
                for constraint in goal.constraints
            )
            pass_ok = not goal.require_no_pass_regression or (delta_in >= 0 and delta_ho >= 0)
            non_degrading = goal.non_degrading(current_in, candidate_in) and goal.non_degrading(
                current_ho,
                candidate_ho,
            )
            holdout_improved = goal.improved(current_ho, candidate_ho)
            if measurement is not None and measurement.enabled:
                estimate_args = {
                    "metric": goal.primary_metric,
                    "direction": goal.direction,
                    "effect_floor": goal.min_delta,
                    "contract": measurement,
                    "familywise_comparisons": familywise_comparisons,
                }
                train_estimate = matched_question_estimate(
                    current=current_train,
                    candidate=candidate_train,
                    **estimate_args,
                )
                holdout_estimate = matched_question_estimate(
                    current=current_holdout,
                    candidate=candidate_holdout,
                    **estimate_args,
                )
                non_degrading = (
                    train_estimate.supports_non_degradation
                    and holdout_estimate.supports_non_degradation
                )
                holdout_improved = holdout_estimate.supports_improvement
            improved = (
                holdout_improved
                if goal.require_holdout_improvement
                else goal.improved(current_in, candidate_in) or holdout_improved
            )
            accepted = constraints_ok and pass_ok and non_degrading and improved
            improvement_rule = (
                "holdout improvement required"
                if goal.require_holdout_improvement
                else "either split may improve"
            )
            uncertainty = ""
            if train_estimate is not None and holdout_estimate is not None:
                uncertainty = (
                    f"; matched CI train=[{train_estimate.ci_low:+.4f},"
                    f"{train_estimate.ci_high:+.4f}] validation=[{holdout_estimate.ci_low:+.4f},"
                    f"{holdout_estimate.ci_high:+.4f}]"
                )
            reason = (
                f"objective gate ({goal.primary_metric}, {goal.direction}): "
                f"Δ_in={delta_in_score:+.4f} Δ_ho={delta_ho_score:+.4f}; "
                f"{improvement_rule}{uncertainty}; "
                + ("accepted" if accepted else "constraint, regression, or effect floor failed")
            )
    elif gate == "combined":
        accepted = (delta_in + delta_ho) > 0
        reason = (
            f"combined gate: Δ_in={delta_in:+d} Δ_ho={delta_ho:+d} "
            f"sum={delta_in + delta_ho:+d} "
            + ("improved" if accepted else "did not improve")
        )
    else:
        accepted = delta_in >= 0 and delta_ho >= 0 and max(delta_in, delta_ho) > 0
        if accepted:
            reason = f"conservative gate: Δ_in={delta_in:+d} Δ_ho={delta_ho:+d}; no regression and at least one gain"
        elif delta_in < 0 or delta_ho < 0:
            regressed = "train" if delta_in < 0 else "holdout"
            if delta_in < 0 and delta_ho < 0:
                regressed = "train and holdout"
            reason = f"conservative gate: Δ_in={delta_in:+d} Δ_ho={delta_ho:+d}; {regressed} regressed"
        else:
            reason = f"conservative gate: Δ_in={delta_in:+d} Δ_ho={delta_ho:+d}; no split improved"

    return GateDecision(
        gate=gate,
        accepted=accepted,
        reason=reason,
        delta_in=delta_in,
        delta_ho=delta_ho,
        delta_in_rate=delta_in_rate,
        delta_ho_rate=delta_ho_rate,
        delta_in_score=delta_in_score,
        delta_ho_score=delta_ho_score,
        train_estimate=train_estimate,
        holdout_estimate=holdout_estimate,
    )
