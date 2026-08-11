"""Repeated split evaluation (P0-1).

Upstream better-harness runs every candidate exactly once per split. On noisy
benchmarks (Terminal-Bench, anything with timeouts or flaky containers) a single
rollout per candidate makes accept/reject close to a coin flip: run-to-run noise
is routinely larger than the effect being measured, so noise gets promoted into
the main line and the loop then evolves on top of it.

This module runs each split ``repeats`` times and aggregates the runs into one
``SplitResult`` whose ``passed``/``total`` count *attempts*, not cases. The
resulting ``correctness`` is therefore a pass@1 estimate over ``n_cases * repeats``
attempts.

Per-case aggregation uses four statuses:

``passed``
    every measured repeat passed (stable pass)
``failed``
    every measured repeat failed (stable fail)
``flaky``
    mixed
``apparatus``
    every repeat failed to measure anything (see :mod:`better_harness.apparatus`)

Apparatus repeats are dropped before aggregation, so they neither score nor
dilute: ``total`` counts *measured* attempts only, and the apparatus attempts are
reported separately on ``SplitResult.apparatus``.

``CaseOutcome.passed`` is ``status == "passed"``, so ``passing_case_ids()`` keeps
its "stably passing" meaning and flaky cases never look like wins.

The runners are untouched: repeats are isolated by handing the runner a
``_RepeatLayout`` proxy that only rewrites ``split_dir``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from better_harness.apparatus import STATUS_APPARATUS
from better_harness.core import CaseOutcome, Experiment, RunLayout, SplitResult, Variant

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence

STATUS_STABLE = "passed"  # every repeat succeeded
STATUS_BROKEN = "failed"  # every repeat failed
STATUS_FLAKY = "flaky"  # mixed across repeats


class SplitRunner(Protocol):
    """Minimal runner protocol used by :func:`run_split_repeated`."""

    def run_split(
        self,
        *,
        experiment: Experiment,
        variant: Variant,
        split: str,
        layout: RunLayout,
        reuse_existing: bool = False,
    ) -> SplitResult:
        """Run one split once."""
        ...


class _RepeatLayout:
    """Proxy layout that scopes one repeat into its own ``repNN`` directory.

    Everything except :meth:`split_dir` delegates to the wrapped layout, so the
    variant JSON and the shared ``_runtime`` sitecustomize are reused across
    repeats rather than rewritten per repeat.
    """

    def __init__(self, base: RunLayout, repeat: int) -> None:
        self._base = base
        self._repeat = repeat

    def split_dir(self, *, variant_key: str, split: str) -> Path:
        """Return the repeat-scoped split directory."""
        return self._base.split_dir(variant_key=variant_key, split=split) / f"rep{self._repeat:02d}"

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


def _first(values: Sequence[str | None]) -> str | None:
    for value in values:
        if value:
            return value
    return None


def aggregate_split_results(
    results: Sequence[SplitResult],
    *,
    run_dir: Path,
) -> SplitResult:
    """Aggregate repeated runs of one split into a single ``SplitResult``.

    ``passed`` becomes the number of successful *attempts* across every repeat and
    ``total`` the number of *measured* attempts (``n_cases * repeats`` minus the
    apparatus failures), so ``correctness`` is a pass@1 estimate over what was
    actually observed. Raises ``ValueError`` on an empty sequence.
    """
    if not results:
        msg = "aggregate_split_results requires at least one result"
        raise ValueError(msg)
    if len(results) == 1:
        first = results[0]
        return SplitResult(
            split=first.split,
            variant=first.variant,
            model=first.model,
            passed=first.passed,
            total=first.total,
            score=first.score,
            returncode=first.returncode,
            run_dir=str(run_dir),
            outcomes=first.outcomes,
            apparatus=first.apparatus,
            fingerprints=first.fingerprints,
        )

    order: list[str] = []
    by_case: dict[str, list[CaseOutcome]] = {}
    for result in results:
        for outcome in result.outcomes:
            if outcome.case_id not in by_case:
                by_case[outcome.case_id] = []
                order.append(outcome.case_id)
            by_case[outcome.case_id].append(outcome)

    aggregated: list[CaseOutcome] = []
    attempts = 0
    successes = 0
    apparatus_attempts = 0
    for case_id in order:
        outcomes = by_case[case_id]
        # Apparatus repeats measured nothing, so they neither score nor dilute.
        # A case whose every repeat was apparatus is reported as apparatus rather
        # than as a failure: no evidence about the harness was collected for it.
        measured = [outcome for outcome in outcomes if not outcome.is_apparatus]
        apparatus_attempts += len(outcomes) - len(measured)
        if not measured:
            evidence = outcomes[0]
            aggregated.append(
                CaseOutcome(
                    case_id=case_id,
                    split=evidence.split,
                    stratum=evidence.stratum,
                    status=STATUS_APPARATUS,
                    score=0.0,
                    duration_s=sum(outcome.duration_s for outcome in outcomes) / len(outcomes),
                    failure_message=_first([outcome.failure_message for outcome in outcomes]),
                    artifacts_dir=evidence.artifacts_dir,
                    trace_ref=_first([outcome.trace_ref for outcome in outcomes]),
                )
            )
            continue
        hits = sum(1 for outcome in measured if outcome.passed)
        attempts += len(measured)
        successes += hits
        if hits == len(measured):
            status = STATUS_STABLE
        elif hits == 0:
            status = STATUS_BROKEN
        else:
            status = STATUS_FLAKY
        # Point the outer agent at a real failing repeat when one exists, so it
        # still reads a genuine failure trace rather than a passing one.
        evidence = next(
            (outcome for outcome in measured if not outcome.passed),
            measured[0],
        )
        aggregated.append(
            CaseOutcome(
                case_id=case_id,
                split=evidence.split,
                stratum=evidence.stratum,
                status=status,
                score=hits / len(measured),
                duration_s=sum(outcome.duration_s for outcome in measured) / len(measured),
                failure_message=_first([outcome.failure_message for outcome in measured]),
                artifacts_dir=evidence.artifacts_dir,
                trace_ref=_first([outcome.trace_ref for outcome in measured]),
            )
        )

    return SplitResult(
        split=results[0].split,
        variant=results[0].variant,
        model=results[0].model,
        passed=successes,
        total=attempts,
        score=float(successes),
        returncode=max(result.returncode for result in results),
        run_dir=str(run_dir),
        outcomes=tuple(aggregated),
        apparatus=apparatus_attempts,
        fingerprints=tuple(sorted({fp for result in results for fp in result.fingerprints})),
    )


def write_repeat_detail(
    *,
    run_dir: Path,
    results: Sequence[SplitResult],
    aggregated: SplitResult,
) -> None:
    """Write per-repeat detail next to the aggregated result."""
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "repeats": len(results),
        "aggregate": {
            "passed": aggregated.passed,
            "total": aggregated.total,
            "correctness": aggregated.correctness,
            "apparatus": aggregated.apparatus,
            "apparatus_rate": aggregated.apparatus_rate,
            "measurable": aggregated.measurable,
        },
        "per_repeat": [
            {
                "repeat": index,
                "passed": result.passed,
                "total": result.total,
                "correctness": result.correctness,
                "run_dir": result.run_dir,
            }
            for index, result in enumerate(results)
        ],
        "per_case": [
            {
                "case_id": outcome.case_id,
                "stratum": outcome.stratum,
                "status": outcome.status,
                "pass_fraction": outcome.score,
            }
            for outcome in aggregated.outcomes
        ],
    }
    (run_dir / "repeats.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def run_split_repeated(  # noqa: PLR0913 - mirrors the runner.run_split signature
    runner: SplitRunner,
    *,
    experiment: Experiment,
    variant: Variant,
    split: str,
    layout: RunLayout,
    reuse_existing: bool = False,
    repeats: int | None = None,
) -> SplitResult:
    """Run one split ``repeats`` times and return the aggregated result."""
    count = experiment.repeats if repeats is None else repeats
    count = max(1, int(count))
    base_dir = layout.split_dir(variant_key=variant.key, split=split)

    results: list[SplitResult] = []
    for index in range(count):
        scoped = _RepeatLayout(layout, index) if count > 1 else layout
        results.append(
            runner.run_split(
                experiment=experiment,
                variant=variant,
                split=split,
                layout=scoped,  # type: ignore[arg-type]
                reuse_existing=reuse_existing,
            )
        )

    aggregated = aggregate_split_results(results, run_dir=base_dir)
    if count > 1:
        base_dir.mkdir(parents=True, exist_ok=True)
        aggregated.save(base_dir / "result.json")
        write_repeat_detail(run_dir=base_dir, results=results, aggregated=aggregated)
    return aggregated
