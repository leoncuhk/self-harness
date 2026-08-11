"""Apparatus-failure partition (Phase 0).

The outcome variable has to be a three-way partition, not a binary one:

``passed`` / ``failed``
    the agent ran and the verifier judged it. Real evidence about the harness.
``apparatus``
    *we failed to measure*. The junit file was unparseable, the transport gave
    out after every retry, the process was killed. Nothing was learned about the
    harness, so these belong in neither the numerator nor the denominator.

Collapsing the third class into ``failed`` makes every split score a mixture of
two processes with an unknown weight, and biases it downward by exactly the
apparatus rate. Measured on ``runs/mvp2-baseline``: 20 of 63 recorded failures
were junit-parse misses and were scored 0 — including all 20 scorecard rollouts,
which is why every ``final_scorecard`` in the repo reads 0/20 against true
baselines of 17-18/20.

Two neighbouring classes are deliberately *not* apparatus:

step-budget exhaustion (``GraphRecursionError``)
    The agent ran, spent its whole step budget, and delivered nothing. That is a
    task failure and it counts. What was wrong was never the classification — it
    was that the budget lives in a frozen constant no editable surface can reach,
    so the proposer could see the failure and not act on it. The fix is a runtime
    policy surface, not a denominator change.
harness-invalid (surfaces fail to import/execute)
    The proposer wrote code that does not run. That is a real defect of the
    candidate and must not be excused; it should be caught by the smoke gate
    before a full evaluation is spent on it, not forgiven afterwards.
"""

from __future__ import annotations

import re

STATUS_APPARATUS = "apparatus"

# Ordered: first match wins, so put the specific patterns first.
APPARATUS_RULES: tuple[tuple[str, str], ...] = (
    (r"case missing from junit\.xml|no such file.*junit|failed to parse junit", "junit_unreadable"),
    (r"connection error|server disconnected|remoteprotocolerror|apiconnectionerror", "transport"),
    (r"connection reset|connection aborted|broken pipe", "transport"),
    (r"\b(502|503|504)\b.*(bad gateway|unavailable|gateway timeout)", "transport"),
    (r"killed by signal|process was killed|signal 9|sigkill", "process_killed"),
    (r"no space left on device|out of memory|oomkilled", "host_resource"),
)

_COMPILED = tuple((re.compile(pattern, re.IGNORECASE), kind) for pattern, kind in APPARATUS_RULES)


def apparatus_kind(failure_message: str | None) -> str | None:
    """Return the apparatus-failure kind for a message, or None if it is a real outcome."""
    if not failure_message:
        return None
    for pattern, kind in _COMPILED:
        if pattern.search(failure_message):
            return kind
    return None


def apparatus_rate(*, apparatus: int, measured: int) -> float:
    """Return apparatus failures as a fraction of all attempted evaluations."""
    attempted = apparatus + measured
    return 0.0 if attempted == 0 else apparatus / attempted


DEFAULT_MAX_APPARATUS_RATE = 0.20


def is_measurable(*, apparatus: int, measured: int, max_rate: float = DEFAULT_MAX_APPARATUS_RATE) -> bool:
    """Return whether enough of a split was actually measured to decide anything.

    Excluding apparatus failures from the denominator is right for the estimate
    and wrong for the *comparison* if it is left unchecked: a candidate whose
    evaluation mostly failed to run would be scored on whatever handful of cases
    happened to complete, and a small favourable sample can clear a gate that a
    full evaluation would not. Past the threshold the evaluation is treated as
    unmeasured — it can be re-run, it can be reported, it cannot promote.
    """
    if measured == 0:
        return False
    return apparatus_rate(apparatus=apparatus, measured=measured) <= max_rate
