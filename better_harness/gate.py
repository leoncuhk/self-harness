"""Promotion gates (P0-2).

Upstream better-harness promotes a candidate when the *combined* train + holdout
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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from better_harness.core import SplitResult

VALID_GATES = ("conservative", "combined")


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize the decision."""
        return asdict(self)


def _deltas(current: SplitResult, candidate: SplitResult) -> tuple[int, float]:
    return (
        candidate.passed - current.passed,
        candidate.correctness - current.correctness,
    )


def decide(
    *,
    gate: str,
    current_train: SplitResult,
    current_holdout: SplitResult,
    candidate_train: SplitResult,
    candidate_holdout: SplitResult,
) -> GateDecision:
    """Return the promotion decision for one candidate."""
    if gate not in VALID_GATES:
        msg = f"invalid gate {gate!r}; expected one of {VALID_GATES}"
        raise ValueError(msg)

    delta_in, delta_in_rate = _deltas(current_train, candidate_train)
    delta_ho, delta_ho_rate = _deltas(current_holdout, candidate_holdout)

    if gate == "combined":
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
    )
