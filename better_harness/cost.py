"""Cost and latency budget (P1-4).

Upstream better-harness gates on pass rate alone. Nothing stops a candidate from
buying its improvement: add a verification pass that triples the tool calls, widen
a retry loop, or split one step into five. Pass rate goes up, the gate approves,
and the harness quietly becomes ten times more expensive to run. On a real
workload that is a regression, not a win — and the loop has no way to see it.

This module turns cost into a **veto**. A candidate that passes the correctness
gate is still rejected if it exceeds the configured spend or latency budget.
That makes cost a first-class constraint instead of a footnote in the report,
and it is the multi-objective dimension (quality x cost) that Meta-Harness
optimises explicitly.

Collection is best-effort and requires no runner changes:

- **Latency** always works: ``CaseOutcome.duration_s`` is already populated, so
  total and p95 wall clock come for free.
- **Tokens and money** are read post-hoc from the ``summary.json`` the runners
  already write into each case's artifacts directory. Key names vary by runner
  and by model provider, so they are configurable and simply absent when the
  runner does not report them.

Absent token data is reported as ``None`` and never silently treated as zero: a
budget you cannot measure must not read as a budget you are inside of.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence

    from better_harness.core import SplitResult

DEFAULT_TOKEN_KEYS: tuple[str, ...] = (
    "total_tokens",
    "tokens",
    "token_count",
    "usage.total_tokens",
    "usage.input_tokens+usage.output_tokens",
)
DEFAULT_COST_KEYS: tuple[str, ...] = ("cost_usd", "cost", "total_cost", "usage.cost_usd")

# Defaults are permissive on purpose: they exist to catch a blow-up, not to
# micro-manage a well-behaved loop. A 50% spend increase for a real correctness
# gain is usually a trade worth making; a 3x increase almost never is.
DEFAULT_MAX_COST_GROWTH = 1.5
DEFAULT_MAX_LATENCY_GROWTH = 1.5
# Wall clock is a weak proxy for spend: it moves with machine load, cache state,
# and container scheduling. A ratio over sub-second runs is pure noise, so the
# latency veto only engages once the run is long enough for the ratio to mean
# something. Token or cost data, when the runner reports it, is always preferred.
DEFAULT_MIN_LATENCY_S = 30.0


def _dig(payload: Any, dotted: str) -> Any:
    current = payload
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _lookup(payload: dict[str, Any], keys: Sequence[str]) -> float | None:
    for key in keys:
        if "+" in key:
            parts = [_dig(payload, part) for part in key.split("+")]
            if all(isinstance(part, (int, float)) for part in parts):
                return float(sum(parts))  # type: ignore[arg-type]
            continue
        value = _dig(payload, key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _percentile(values: Sequence[float], fraction: float) -> float:
    """Return the nearest-rank percentile of ``values``."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(fraction * (len(ordered) - 1))))
    return ordered[index]


@dataclass(frozen=True)
class CostProfile:
    """Spend and latency for one split."""

    attempts: int
    total_duration_s: float
    p95_duration_s: float
    total_tokens: float | None
    total_cost_usd: float | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the profile."""
        return asdict(self)

    def spend(self) -> tuple[str, float] | None:
        """Return the best available spend metric as ``(name, value)``."""
        if self.total_cost_usd is not None:
            return ("cost_usd", self.total_cost_usd)
        if self.total_tokens is not None:
            return ("tokens", self.total_tokens)
        return None


def profile_split(
    result: SplitResult,
    *,
    token_keys: Sequence[str] = DEFAULT_TOKEN_KEYS,
    cost_keys: Sequence[str] = DEFAULT_COST_KEYS,
) -> CostProfile:
    """Build a cost profile for one split result."""
    durations = [outcome.duration_s for outcome in result.outcomes]
    tokens: float | None = None
    cost: float | None = None

    for outcome in result.outcomes:
        if not outcome.artifacts_dir:
            continue
        summary_path = Path(outcome.artifacts_dir) / "summary.json"
        if not summary_path.exists():
            continue
        try:
            payload = json.loads(summary_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if (value := _lookup(payload, token_keys)) is not None:
            tokens = value if tokens is None else tokens + value
        if (value := _lookup(payload, cost_keys)) is not None:
            cost = value if cost is None else cost + value

    return CostProfile(
        attempts=result.total,
        total_duration_s=sum(durations),
        p95_duration_s=_percentile(durations, 0.95),
        total_tokens=tokens,
        total_cost_usd=cost,
    )


@dataclass(frozen=True)
class BudgetDecision:
    """Outcome of the cost veto."""

    within_budget: bool
    reason: str
    spend_growth: float | None
    latency_growth: float | None
    max_cost_growth: float
    max_latency_growth: float
    current: dict[str, Any]
    candidate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the decision."""
        return asdict(self)


def _growth(before: float | None, after: float | None) -> float | None:
    if before is None or after is None or before <= 0:
        return None
    return after / before


def check_budget(
    *,
    current: Sequence[CostProfile],
    candidate: Sequence[CostProfile],
    max_cost_growth: float = DEFAULT_MAX_COST_GROWTH,
    max_latency_growth: float = DEFAULT_MAX_LATENCY_GROWTH,
    min_latency_s: float = DEFAULT_MIN_LATENCY_S,
) -> BudgetDecision:
    """Veto a candidate that buys its correctness gain with spend or latency."""
    current_duration = sum(profile.total_duration_s for profile in current)
    candidate_duration = sum(profile.total_duration_s for profile in candidate)
    current_p95 = max((profile.p95_duration_s for profile in current), default=0.0)
    candidate_p95 = max((profile.p95_duration_s for profile in candidate), default=0.0)

    def _total(profiles: Sequence[CostProfile], field: str) -> float | None:
        values = [getattr(profile, field) for profile in profiles]
        if any(value is None for value in values):
            return None
        return float(sum(values))  # type: ignore[arg-type]

    current_cost = _total(current, "total_cost_usd")
    candidate_cost = _total(candidate, "total_cost_usd")
    current_tokens = _total(current, "total_tokens")
    candidate_tokens = _total(candidate, "total_tokens")

    spend_growth = _growth(current_cost, candidate_cost)
    spend_metric = "cost_usd"
    if spend_growth is None:
        spend_growth = _growth(current_tokens, candidate_tokens)
        spend_metric = "tokens"

    latency_growth = _growth(current_duration, candidate_duration)
    p95_growth = _growth(current_p95, candidate_p95)

    failures: list[str] = []
    if spend_growth is not None and spend_growth > max_cost_growth:
        failures.append(f"{spend_metric} {spend_growth:.2f}x > {max_cost_growth:.2f}x")
    latency_measurable = candidate_duration >= min_latency_s
    if latency_measurable:
        if latency_growth is not None and latency_growth > max_latency_growth:
            failures.append(f"wall clock {latency_growth:.2f}x > {max_latency_growth:.2f}x")
        if p95_growth is not None and p95_growth > max_latency_growth:
            failures.append(f"p95 latency {p95_growth:.2f}x > {max_latency_growth:.2f}x")

    if failures:
        reason = "cost veto: " + "; ".join(failures)
    elif spend_growth is None:
        measured = "latency" if latency_measurable else "nothing"
        reason = (
            f"cost veto: not enforced ({measured} measurable); "
            "runner reported no token or cost data"
        )
    else:
        reason = f"cost veto: within budget ({spend_metric} {spend_growth:.2f}x)"

    return BudgetDecision(
        within_budget=not failures,
        reason=reason,
        spend_growth=spend_growth,
        latency_growth=latency_growth,
        max_cost_growth=max_cost_growth,
        max_latency_growth=max_latency_growth,
        current={
            "duration_s": current_duration,
            "p95_duration_s": current_p95,
            "tokens": current_tokens,
            "cost_usd": current_cost,
        },
        candidate={
            "duration_s": candidate_duration,
            "p95_duration_s": candidate_p95,
            "tokens": candidate_tokens,
            "cost_usd": candidate_cost,
        },
    )
