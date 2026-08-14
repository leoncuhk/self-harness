"""Immutable goal and metric contracts for self-harness experiments."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

VALID_DIRECTIONS = ("maximize", "minimize")


@dataclass(frozen=True)
class MetricConstraint:
    """One non-negotiable metric threshold."""

    metric: str
    minimum: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        """Validate that the threshold is meaningful."""
        if self.minimum is None and self.maximum is None:
            msg = f"constraint {self.metric!r} needs minimum or maximum"
            raise ValueError(msg)
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            msg = f"constraint {self.metric!r} has minimum above maximum"
            raise ValueError(msg)

    def accepts(self, value: float | None) -> bool:
        """Return whether a measured value satisfies the threshold."""
        if value is None:
            return False
        if self.minimum is not None and value < self.minimum:
            return False
        return self.maximum is None or value <= self.maximum


@dataclass(frozen=True)
class GoalContract:
    """Frozen definition of what an optimization run is allowed to optimize."""

    primary_metric: str = "score"
    direction: str = "maximize"
    min_delta: float = 0.0
    require_no_pass_regression: bool = True
    constraints: tuple[MetricConstraint, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate the immutable objective definition."""
        if self.direction not in VALID_DIRECTIONS:
            msg = f"invalid goal direction {self.direction!r}; expected {VALID_DIRECTIONS}"
            raise ValueError(msg)
        if not self.primary_metric.strip():
            msg = "goal.primary_metric cannot be empty"
            raise ValueError(msg)
        if self.min_delta < 0:
            msg = "goal.min_delta cannot be negative"
            raise ValueError(msg)

    def improvement(self, before: float, after: float) -> float:
        """Return a positive number when ``after`` improves the objective."""
        return after - before if self.direction == "maximize" else before - after

    def improved(self, before: float, after: float) -> bool:
        """Return whether an objective change clears the declared effect floor."""
        delta = self.improvement(before, after)
        return delta > self.min_delta and not math.isclose(
            delta,
            self.min_delta,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )

    def non_degrading(self, before: float, after: float) -> bool:
        """Return whether an objective did not move in the wrong direction."""
        return self.improvement(before, after) >= 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the contract into run manifests."""
        return asdict(self)


def load_goal_contract(payload: dict[str, Any] | None) -> GoalContract:
    """Load a goal contract from the optional ``[goal]`` config table."""
    raw = dict(payload or {})
    constraints = tuple(
        MetricConstraint(
            metric=str(item["metric"]),
            minimum=None if item.get("minimum") is None else float(item["minimum"]),
            maximum=None if item.get("maximum") is None else float(item["maximum"]),
        )
        for item in raw.pop("constraints", ())
    )
    return GoalContract(
        primary_metric=str(raw.pop("primary_metric", "score")),
        direction=str(raw.pop("direction", "maximize")),
        min_delta=float(raw.pop("min_delta", 0.0)),
        require_no_pass_regression=bool(raw.pop("require_no_pass_regression", True)),
        constraints=constraints,
    )
