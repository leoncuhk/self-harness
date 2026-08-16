"""Matched-question uncertainty estimates for promotion decisions.

Repeated rollouts reduce noise, but an aggregate mean alone does not say whether a
candidate is distinguishable from its incumbent. This module compares identical
question ids, treats questions as resampling clusters, and reports a deterministic
bootstrap interval for mean improvement.

The comparison is matched by question, not by hidden model randomness. Unless a
provider exposes and honours a seed, incumbent and candidate rollouts remain
independent stochastic executions within each question.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from statistics import NormalDist, mean, stdev
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from self_harness.core import CaseOutcome, SplitResult


@dataclass(frozen=True)
class MeasurementContract:
    """Frozen uncertainty policy used by the objective promotion gate."""

    enabled: bool = False
    confidence: float = 0.95
    bootstrap_samples: int = 10_000
    minimum_pairs: int = 4
    seed: int = 0

    def __post_init__(self) -> None:
        """Reject policies that cannot support a meaningful interval."""
        if not 0.5 < self.confidence < 1.0:
            msg = "measurement.confidence must be between 0.5 and 1"
            raise ValueError(msg)
        if self.bootstrap_samples < 100:
            msg = "measurement.bootstrap_samples must be at least 100"
            raise ValueError(msg)
        if self.minimum_pairs < 2:
            msg = "measurement.minimum_pairs must be at least 2"
            raise ValueError(msg)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the frozen policy."""
        return asdict(self)


@dataclass(frozen=True)
class MatchedEstimate:
    """One matched-question estimate expressed in improvement direction."""

    metric: str
    pairs: int
    mean_delta: float
    ci_low: float
    ci_high: float
    confidence: float
    familywise_comparisons: int
    effect_floor: float
    minimum_detectable_effect: float | None
    missing_current: tuple[str, ...]
    missing_candidate: tuple[str, ...]
    sufficient_pairs: bool

    @property
    def complete_pairs(self) -> bool:
        """Return whether neither arm lost a question from the matched matrix."""
        return not self.missing_current and not self.missing_candidate

    @property
    def supports_non_degradation(self) -> bool:
        """Return whether the simultaneous interval rules out regression."""
        return self.sufficient_pairs and self.complete_pairs and self.ci_low >= 0.0

    @property
    def supports_improvement(self) -> bool:
        """Return whether the interval clears the pre-registered effect floor."""
        return self.sufficient_pairs and self.complete_pairs and self.ci_low > self.effect_floor

    def to_dict(self) -> dict[str, Any]:
        """Serialize the estimate, including derived decisions."""
        return {
            **asdict(self),
            "complete_pairs": self.complete_pairs,
            "supports_non_degradation": self.supports_non_degradation,
            "supports_improvement": self.supports_improvement,
        }


def load_measurement_contract(payload: dict[str, Any] | None) -> MeasurementContract:
    """Load the optional ``[measurement]`` table."""
    raw = dict(payload or {})
    contract = MeasurementContract(
        enabled=bool(raw.pop("enabled", False)),
        confidence=float(raw.pop("confidence", 0.95)),
        bootstrap_samples=int(raw.pop("bootstrap_samples", 10_000)),
        minimum_pairs=int(raw.pop("minimum_pairs", 4)),
        seed=int(raw.pop("seed", 0)),
    )
    if raw:
        msg = f"unknown measurement settings: {sorted(raw)}"
        raise ValueError(msg)
    return contract


def _case_metric(outcome: CaseOutcome, metric: str) -> float | None:
    if outcome.is_apparatus:
        return None
    if metric == "score":
        return float(outcome.score)
    if metric in {"correctness", "passed"}:
        return float(outcome.passed)
    value = outcome.metrics.get(metric)
    return None if value is None else float(value)


def _quantile(ordered: list[float], probability: float) -> float:
    if not ordered:
        return 0.0
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def matched_question_estimate(  # noqa: PLR0913 - complete frozen comparison contract
    *,
    current: SplitResult,
    candidate: SplitResult,
    metric: str,
    direction: str,
    effect_floor: float,
    contract: MeasurementContract,
    familywise_comparisons: int = 1,
) -> MatchedEstimate:
    """Estimate improvement from matched question-level outcomes.

    Bonferroni adjustment uses the number of candidate comparisons planned before
    the run. This is intentionally conservative under adaptive candidate search.
    """
    if direction not in {"maximize", "minimize"}:
        msg = f"invalid direction {direction!r}"
        raise ValueError(msg)
    comparisons = max(1, int(familywise_comparisons))
    current_values = {
        outcome.case_id: value
        for outcome in current.outcomes
        if (value := _case_metric(outcome, metric)) is not None
    }
    candidate_values = {
        outcome.case_id: value
        for outcome in candidate.outcomes
        if (value := _case_metric(outcome, metric)) is not None
    }
    shared = sorted(current_values.keys() & candidate_values.keys())
    sign = 1.0 if direction == "maximize" else -1.0
    deltas = [sign * (candidate_values[key] - current_values[key]) for key in shared]
    point = mean(deltas) if deltas else 0.0

    alpha = (1.0 - contract.confidence) / comparisons
    rng = random.Random(contract.seed)  # noqa: S311 - deterministic statistical resampling
    if deltas:
        draws = sorted(
            mean(rng.choice(deltas) for _ in deltas)
            for _ in range(contract.bootstrap_samples)
        )
        ci_low = _quantile(draws, alpha / 2.0)
        ci_high = _quantile(draws, 1.0 - alpha / 2.0)
    else:
        ci_low = ci_high = 0.0

    if len(deltas) >= 2:
        standard_error = stdev(deltas) / math.sqrt(len(deltas))
        critical = NormalDist().inv_cdf(1.0 - alpha / 2.0)
        minimum_detectable_effect = effect_floor + critical * standard_error
    else:
        minimum_detectable_effect = None

    return MatchedEstimate(
        metric=metric,
        pairs=len(deltas),
        mean_delta=point,
        ci_low=ci_low,
        ci_high=ci_high,
        confidence=1.0 - alpha,
        familywise_comparisons=comparisons,
        effect_floor=effect_floor,
        minimum_detectable_effect=minimum_detectable_effect,
        missing_current=tuple(sorted(candidate_values.keys() - current_values.keys())),
        missing_candidate=tuple(sorted(current_values.keys() - candidate_values.keys())),
        sufficient_pairs=len(deltas) >= contract.minimum_pairs,
    )
