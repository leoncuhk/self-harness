"""Edit guard (P1-3).

Upstream better-harness constrains *which* surfaces the outer agent may edit but
places no constraint on *what* it writes into them, and its README is explicit
that the visible/private split "is not a hard sandbox boundary yet". That leaves
the cheapest paths to a higher score wide open:

1. hard-code the eval's own case ids or test literals into harness text
2. edit the model, temperature, token budget, or reasoning budget
3. point the harness at the verifier or the test files
4. grow the harness without bound until something sticks

None of those generalize, and the first three are the difference between
"learned engineering experience" and "memorised the answer key". This module
rejects a candidate **before** it costs an eval run.

The guard is a static check over the candidate's surface values. It is not a
sandbox: it cannot stop code from doing something at runtime. It closes the
cheap, obvious holes, and it makes every rejection auditable.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence

    from better_harness.core import Experiment, Variant

VIOLATION_CASE_LEAK = "case_id_leak"
VIOLATION_FORBIDDEN = "forbidden_pattern"
VIOLATION_BLOAT = "surface_bloat"
VIOLATION_UNDECLARED = "undeclared_surface"

# Knobs that decide how much compute the run is allowed to spend, plus anything
# that touches the evaluator. Optimising these is not harness engineering; it is
# either buying the score or grading your own homework.
DEFAULT_FORBIDDEN_PATTERNS: tuple[str, ...] = (
    r"\b(temperature|top_p|top_k)\s*=",
    r"\bmax_tokens\b\s*[=:]",
    r"\b(reasoning_effort|thinking_budget|reasoning_budget|budget_tokens)\b\s*[=:]",
    r"\bmodel\s*=\s*[\"'][\w./:-]+[\"']",
    # No \b before the dashes: a word boundary cannot exist between a space and
    # a hyphen, so \b-- never matches anything.
    r"\b(pytest|harbor)\b.*(?<![\w-])--?[a-z-]*(deselect|ignore|skip|maxfail|last-failed)\b",
    r"\bconftest\.py\b",
    r"\bverifier\b|\breward\.txt\b",
    r"\bmonkeypatch\b|\bunittest\.mock\b",
)

# Default ceiling on total harness size relative to the baseline. Harness bloat
# is the standard failure mode of these loops: context grows every iteration and
# nobody notices until the agent is drowning in its own instructions.
DEFAULT_MAX_GROWTH = 3.0
# A ratio alone is meaningless against a tiny seed: a 78-byte baseline exceeds
# any multiplier the moment the proposer writes a real sentence. Bloat requires
# both the ratio *and* an absolute size worth caring about.
DEFAULT_MIN_BLOAT_BYTES = 4096


@dataclass(frozen=True)
class Violation:
    """One guard violation."""

    kind: str
    surface: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        """Serialize the violation."""
        return asdict(self)


@dataclass(frozen=True)
class GuardReport:
    """Result of guarding one candidate variant."""

    violations: tuple[Violation, ...]
    baseline_bytes: int
    candidate_bytes: int
    max_growth: float

    @property
    def ok(self) -> bool:
        """Return whether the candidate may proceed to evaluation."""
        return not self.violations

    @property
    def growth(self) -> float:
        """Return candidate size relative to the baseline."""
        if self.baseline_bytes == 0:
            return 1.0
        return self.candidate_bytes / self.baseline_bytes

    def reason(self) -> str:
        """Render a one-line rejection reason."""
        if self.ok:
            return "edit guard: clean"
        heads = "; ".join(f"{item.kind} in {item.surface}: {item.detail}" for item in self.violations[:3])
        suffix = "" if len(self.violations) <= 3 else f" (+{len(self.violations) - 3} more)"
        return f"edit guard: rejected — {heads}{suffix}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report."""
        return {
            "ok": self.ok,
            "baseline_bytes": self.baseline_bytes,
            "candidate_bytes": self.candidate_bytes,
            "growth": self.growth,
            "max_growth": self.max_growth,
            "violations": [item.to_dict() for item in self.violations],
        }


def case_literals(experiment: Experiment) -> set[str]:
    """Return the literals that must never appear in harness text.

    Covers every split, not only the visible one: hard-coding a train case id is
    just as much memorisation as hard-coding a holdout id, and the holdout ids
    appearing at all would mean the private split leaked.
    """
    literals: set[str] = set()
    for case in experiment.cases:
        rendered = case.render(model=experiment.model)
        literals.add(rendered)
        node = rendered.partition("::")[2]
        if node:
            # strip the pytest parametrisation suffix: test_x[model] -> test_x
            literals.add(re.sub(r"\[.*\]$", "", node))
        file_part = rendered.partition("::")[0]
        if file_part and "/" in file_part:
            literals.add(file_part)
    # Very short tokens produce false positives; require something distinctive.
    return {literal for literal in literals if len(literal) >= 8}


def _scan_forbidden(text: str, patterns: Sequence[str]) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            hits.append((pattern, match.group(0)))
    return hits


def check_variant(  # noqa: PLR0913 - every threshold is meant to be overridable per experiment
    *,
    experiment: Experiment,
    baseline: Variant,
    candidate: Variant,
    forbidden_patterns: Sequence[str] | None = None,
    max_growth: float | None = None,
    min_bloat_bytes: int | None = None,
) -> GuardReport:
    """Statically check one candidate variant before it is evaluated."""
    patterns = tuple(DEFAULT_FORBIDDEN_PATTERNS if forbidden_patterns is None else forbidden_patterns)
    growth_limit = DEFAULT_MAX_GROWTH if max_growth is None else max_growth
    literals = case_literals(experiment)

    violations: list[Violation] = []

    for name, value in candidate.values.items():
        if name not in experiment.surfaces:
            violations.append(
                Violation(
                    kind=VIOLATION_UNDECLARED,
                    surface=name,
                    detail="surface is not declared in the experiment config",
                )
            )
            continue

        if value == baseline.values.get(name):
            # Unchanged surfaces inherit whatever the baseline already had; the
            # guard judges the proposer's edits, not the seed it was handed.
            continue

        for literal in sorted(literals):
            if literal in value:
                violations.append(
                    Violation(
                        kind=VIOLATION_CASE_LEAK,
                        surface=name,
                        detail=f"eval case literal {literal!r} written into harness text",
                    )
                )

        for pattern, hit in _scan_forbidden(value, patterns):
            violations.append(
                Violation(
                    kind=VIOLATION_FORBIDDEN,
                    surface=name,
                    detail=f"matched forbidden pattern {pattern!r} at {hit!r}",
                )
            )

    baseline_bytes = sum(len(value.encode()) for value in baseline.values.values())
    candidate_bytes = sum(len(value.encode()) for value in candidate.values.values())
    floor = DEFAULT_MIN_BLOAT_BYTES if min_bloat_bytes is None else min_bloat_bytes
    over_ratio = bool(baseline_bytes) and candidate_bytes > baseline_bytes * growth_limit
    if over_ratio and candidate_bytes >= floor:
        violations.append(
            Violation(
                kind=VIOLATION_BLOAT,
                surface="<all>",
                detail=(
                    f"harness grew to {candidate_bytes}B from {baseline_bytes}B "
                    f"({candidate_bytes / baseline_bytes:.2f}x > {growth_limit:.2f}x limit, "
                    f"floor {floor}B)"
                ),
            )
        )

    return GuardReport(
        violations=tuple(violations),
        baseline_bytes=baseline_bytes,
        candidate_bytes=candidate_bytes,
        max_growth=growth_limit,
    )
