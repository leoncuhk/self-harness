"""Falsifiable predictions and flip attribution (P2-6).

An edit that comes with no prediction cannot be wrong — it can only be kept or
discarded on a number nobody has to explain. AHE's contribution here is to make
every harness edit a **falsifiable assertion**: alongside the diff, the proposer
must commit to failure evidence, a root cause, and the concrete cases it expects
to flip to passing plus the ones it thinks are at risk. The next evaluation then
grades the prediction, not just the pass rate.

Why that matters more than it looks: pass rate tells you *whether* the loop is
improving, prediction accuracy tells you *whether the loop understands why*. A
proposer whose predictions are no better than chance is search, not engineering,
and its gains will not transfer. That signal is available from iteration one,
long before the pass-rate curve says anything, which is what makes it the first
thing worth measuring in a fresh run.

The ledger also surfaces the failure mode that matters most in practice:
**unpredicted regressions**. A case that silently flipped to failing, that the
proposer never flagged as at risk, is evidence the edit had reach the proposer
did not model.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence
    from pathlib import Path

    from self_harness.core import SplitResult

# Parse the fence boundary first, then let json.loads understand braces inside
# quoted strings (for example the FAB tool placeholder ``{{document_key}}``).
_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


@dataclass(frozen=True)
class Prediction:
    """What the proposer committed to before the candidate was evaluated."""

    root_cause: str = ""
    evidence: tuple[str, ...] = ()
    flip_to_pass: tuple[str, ...] = ()
    at_risk: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Return whether the proposer committed to nothing."""
        return not (self.root_cause or self.evidence or self.flip_to_pass or self.at_risk)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the prediction."""
        return asdict(self)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def parse_prediction(*texts: str | None) -> Prediction:
    """Parse the prediction block out of proposal text.

    Scans each text for fenced JSON objects and uses the last one that carries any
    recognised key, so a proposer that writes several code blocks still gets read
    correctly. Returns an empty prediction rather than raising when nothing
    parses: a missing prediction is a fact to record, not a crash.
    """
    best = Prediction()
    for text in texts:
        if not text:
            continue
        for match in _JSON_FENCE.finditer(text):
            try:
                payload = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            candidate = Prediction(
                root_cause=str(payload.get("root_cause", "")).strip(),
                evidence=_string_tuple(payload.get("evidence")),
                flip_to_pass=_string_tuple(payload.get("flip_to_pass")),
                at_risk=_string_tuple(payload.get("at_risk")),
            )
            if not candidate.is_empty:
                best = candidate
    return best


@dataclass(frozen=True)
class FlipReport:
    """Cases that changed stable pass/fail status between two variants."""

    to_pass: tuple[str, ...]
    to_fail: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report."""
        return asdict(self)


def compute_flips(
    *,
    current: Sequence[SplitResult],
    candidate: Sequence[SplitResult],
) -> FlipReport:
    """Compute stable pass/fail flips across a set of splits.

    "Stable" is doing real work here: with repeats enabled a case only counts as
    passing when every repeat passed, so a flaky case never registers as a flip
    in either direction.
    """
    before: set[str] = set()
    after: set[str] = set()
    for result in current:
        before |= result.passing_case_ids()
    for result in candidate:
        after |= result.passing_case_ids()
    return FlipReport(
        to_pass=tuple(sorted(after - before)),
        to_fail=tuple(sorted(before - after)),
    )


@dataclass(frozen=True)
class PredictionScore:
    """How well one prediction survived contact with the evaluation."""

    predicted: int
    hits: int
    misses: tuple[str, ...]
    unexpected_passes: tuple[str, ...]
    unpredicted_regressions: tuple[str, ...]
    warned_regressions: tuple[str, ...]

    @property
    def precision(self) -> float | None:
        """Fraction of predicted flips that actually flipped."""
        return None if self.predicted == 0 else self.hits / self.predicted

    @property
    def recall(self) -> float | None:
        """Fraction of actual flips that were predicted."""
        actual = self.hits + len(self.unexpected_passes)
        return None if actual == 0 else self.hits / actual

    def to_dict(self) -> dict[str, Any]:
        """Serialize the score."""
        return {
            "predicted": self.predicted,
            "hits": self.hits,
            "precision": self.precision,
            "recall": self.recall,
            "misses": list(self.misses),
            "unexpected_passes": list(self.unexpected_passes),
            "unpredicted_regressions": list(self.unpredicted_regressions),
            "warned_regressions": list(self.warned_regressions),
        }


def score_prediction(prediction: Prediction, flips: FlipReport) -> PredictionScore:
    """Grade one prediction against the flips that actually happened."""
    predicted = set(prediction.flip_to_pass)
    at_risk = set(prediction.at_risk)
    actual_pass = set(flips.to_pass)
    actual_fail = set(flips.to_fail)

    return PredictionScore(
        predicted=len(predicted),
        hits=len(predicted & actual_pass),
        misses=tuple(sorted(predicted - actual_pass)),
        unexpected_passes=tuple(sorted(actual_pass - predicted)),
        unpredicted_regressions=tuple(sorted(actual_fail - at_risk)),
        warned_regressions=tuple(sorted(actual_fail & at_risk)),
    )


@dataclass
class LedgerEntry:
    """One row of the change ledger."""

    iteration: int
    variant: str
    accepted: bool
    gate_reason: str
    changed_surfaces: tuple[str, ...] = ()
    prediction: Prediction = field(default_factory=Prediction)
    flips: FlipReport = field(default_factory=lambda: FlipReport((), ()))
    score: PredictionScore | None = None
    guard: dict[str, Any] | None = None
    budget: dict[str, Any] | None = None
    signature_clusters: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entry."""
        return {
            "iteration": self.iteration,
            "variant": self.variant,
            "accepted": self.accepted,
            "gate_reason": self.gate_reason,
            "changed_surfaces": list(self.changed_surfaces),
            "prediction": self.prediction.to_dict(),
            "prediction_made": not self.prediction.is_empty,
            "flips": self.flips.to_dict(),
            "score": None if self.score is None else self.score.to_dict(),
            "guard": self.guard,
            "budget": self.budget,
            "signature_clusters": self.signature_clusters,
        }


def summarize(entries: Sequence[LedgerEntry]) -> dict[str, Any]:
    """Aggregate prediction quality across a run."""
    scored = [entry for entry in entries if entry.score is not None]
    predicted = sum(entry.score.predicted for entry in scored)  # type: ignore[union-attr]
    hits = sum(entry.score.hits for entry in scored)  # type: ignore[union-attr]
    actual = hits + sum(len(entry.score.unexpected_passes) for entry in scored)  # type: ignore[union-attr]
    regressions = sum(len(entry.score.unpredicted_regressions) for entry in scored)  # type: ignore[union-attr]
    return {
        "iterations": len(entries),
        "predictions_made": sum(1 for entry in entries if not entry.prediction.is_empty),
        "accepted": sum(1 for entry in entries if entry.accepted),
        "predicted_flips": predicted,
        "predicted_flips_hit": hits,
        "precision": None if predicted == 0 else hits / predicted,
        "recall": None if actual == 0 else hits / actual,
        "unpredicted_regressions": regressions,
    }


def write_ledger(path: Path, entries: Sequence[LedgerEntry]) -> None:
    """Write ``ledger.json`` and a readable ``ledger.md``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stats = summarize(entries)
    path.write_text(
        json.dumps(
            {"summary": stats, "entries": [entry.to_dict() for entry in entries]},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    def _pct(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.0%}"

    lines = [
        "# Change ledger",
        "",
        f"- Iterations: `{stats['iterations']}` (accepted `{stats['accepted']}`)",
        f"- Predictions made: `{stats['predictions_made']}`",
        f"- Predicted flips hit: `{stats['predicted_flips_hit']}/{stats['predicted_flips']}` "
        f"(precision {_pct(stats['precision'])}, recall {_pct(stats['recall'])})",
        f"- Unpredicted regressions: `{stats['unpredicted_regressions']}`",
        "",
        "| Iter | Variant | Decision | Predicted | Hit | To pass | To fail | Unpredicted regressions |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in entries:
        score = entry.score
        lines.append(
            f"| {entry.iteration} | `{entry.variant}` | "
            f"{'accepted' if entry.accepted else 'rejected'} | "
            f"{0 if score is None else score.predicted} | "
            f"{0 if score is None else score.hits} | "
            f"{len(entry.flips.to_pass)} | {len(entry.flips.to_fail)} | "
            f"{0 if score is None else len(score.unpredicted_regressions)} |"
        )
    path.with_suffix(".md").write_text("\n".join(lines) + "\n")
