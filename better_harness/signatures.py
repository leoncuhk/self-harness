"""Failure signatures and deterministic clustering (P2-5).

Implements the Self-Harness failure signature ``φ(r) = (c, q, m)``
([arXiv:2606.09498](https://arxiv.org/abs/2606.09498)):

``c``
    the terminal verifier-level cause
``q``
    the causal status of the agent's own behaviour
``m``
    the abstract mechanism the failure exposes

Failures cluster by **exact triple equality**. That is deliberate: clustering on
embeddings is not reproducible across runs, and the point of a cluster is that
every member admits the *same* harness-level intervention.

Classification is rule-based over a controlled vocabulary rather than free-form
LLM labelling. A proposer that invents its own vocabulary produces singleton
clusters, which defeats the purpose. Rules that do not match yield ``unknown``
rather than a guess — an honest ``unknown`` is a signal to add a rule, a wrong
label is a signal to chase the wrong fix.

Repeat-aware: a case that passes some repeats and fails others (``flaky``, see
:mod:`better_harness.repeats`) is classified as non-deterministic rather than
being folded into whatever its first failure looked like.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable, Sequence

    from better_harness.core import CaseOutcome, SplitResult

UNKNOWN = "unknown"

# --- c: terminal verifier-level cause -------------------------------------
CAUSE_TIMEOUT = "timeout"
CAUSE_ASSERTION = "assertion_failed"
CAUSE_MISSING_FILE = "missing_file"
CAUSE_COMMAND_ERROR = "command_error"
CAUSE_EXCEPTION = "uncaught_exception"
CAUSE_NO_RESULT = "no_result"
CAUSE_NONDETERMINISTIC = "nondeterministic"

# --- q: causal status of agent behaviour -----------------------------------
AGENT_CAUSED = "agent_caused"
ENVIRONMENT_CAUSED = "environment_caused"
UNDETERMINED = "undetermined"

# --- m: abstract mechanism exposed -----------------------------------------
MECH_NO_VERIFICATION = "no_verification_before_submit"
MECH_RETRY_LOOP = "unbounded_retry_loop"
MECH_PREMATURE_STOP = "premature_stop"
MECH_STATE_LOST = "state_not_persisted"
MECH_TOOL_MISUSE = "tool_misuse"
MECH_CONTEXT_EXHAUSTION = "context_exhaustion"
MECH_FORMAT_VIOLATION = "output_format_violation"
MECH_TRUNCATION = "truncated_read"
MECH_FLAKY = "nondeterministic_behaviour"

# Ordered rules: first match wins, so put the specific patterns first.
CAUSE_RULES: tuple[tuple[str, str], ...] = (
    (r"\btimed?\s*out\b|\btimeout\b|deadline exceeded", CAUSE_TIMEOUT),
    (r"no such file|file not found|filenotfounderror|does not exist", CAUSE_MISSING_FILE),
    (r"assertionerror|\bassert\b|expected .* but got|did not match", CAUSE_ASSERTION),
    (r"non-?zero exit|exit code [1-9]|command failed|returned [1-9]\d* ", CAUSE_COMMAND_ERROR),
    (r"traceback \(most recent call last\)|unhandled exception|raised .*error", CAUSE_EXCEPTION),
    (r"no result|not collected|collection error|missing outcome", CAUSE_NO_RESULT),
)

ENVIRONMENT_RULES: tuple[str, ...] = (
    r"connection (refused|reset|error)",
    r"network is unreachable|dns|temporary failure in name resolution",
    r"rate limit|429|quota exceeded",
    r"container (failed|died|exited)|sandbox (unavailable|failed)",
    r"5\d\d (server )?error|service unavailable",
    r"disk (full|quota)|no space left",
)

MECHANISM_RULES: tuple[tuple[str, str], ...] = (
    (r"same command|repeated(ly)? (ran|called|tried)|loop detected|max iterations", MECH_RETRY_LOOP),
    (r"truncat|pagination|only read the first|offset", MECH_TRUNCATION),
    (r"context (window|length) exceeded|too many tokens|prompt too long", MECH_CONTEXT_EXHAUSTION),
    (r"environment variable|not persisted|lost between|session state", MECH_STATE_LOST),
    (r"invalid (json|format|schema)|could not parse|malformed", MECH_FORMAT_VIOLATION),
    (r"unknown tool|wrong (tool|argument)|invalid argument|missing required", MECH_TOOL_MISUSE),
    (r"stopped early|gave up|no further action|ended without", MECH_PREMATURE_STOP),
)


@dataclass(frozen=True)
class FailureSignature:
    """One ``φ(r) = (c, q, m)`` triple."""

    cause: str
    causal_status: str
    mechanism: str

    @property
    def key(self) -> str:
        """Return a stable string key for the triple."""
        return f"{self.cause}|{self.causal_status}|{self.mechanism}"

    def to_dict(self) -> dict[str, str]:
        """Serialize the signature."""
        return asdict(self)


@dataclass(frozen=True)
class FailureCluster:
    """A group of failures that admit the same harness-level intervention."""

    signature: FailureSignature
    case_ids: tuple[str, ...]
    strata: tuple[str, ...]
    representative_message: str | None

    @property
    def size(self) -> int:
        """Return the number of failing cases in the cluster."""
        return len(self.case_ids)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the cluster."""
        return {
            "signature": self.signature.to_dict(),
            "key": self.signature.key,
            "size": self.size,
            "case_ids": list(self.case_ids),
            "strata": list(self.strata),
            "representative_message": self.representative_message,
        }

    def describe(self) -> str:
        """Render one human- and prompt-readable line."""
        return (
            f"[{self.signature.key}] {self.size} case(s): "
            f"{', '.join(self.case_ids)}"
            + (f" — e.g. {self.representative_message}" if self.representative_message else "")
        )


def _match(rules: Iterable[tuple[str, str]], text: str) -> str | None:
    for pattern, label in rules:
        if re.search(pattern, text):
            return label
    return None


def classify(outcome: CaseOutcome) -> FailureSignature:
    """Classify one failing outcome into ``φ(r) = (c, q, m)``."""
    if outcome.status == "flaky":
        # Mixed across repeats: the harness-level intervention is stabilisation,
        # not whatever the first failing repeat happened to print.
        return FailureSignature(CAUSE_NONDETERMINISTIC, UNDETERMINED, MECH_FLAKY)

    text = (outcome.failure_message or "").lower()
    cause = _match(CAUSE_RULES, text) or (UNKNOWN if text else CAUSE_NO_RESULT)

    environment = any(re.search(pattern, text) for pattern in ENVIRONMENT_RULES)
    if environment:
        causal_status = ENVIRONMENT_CAUSED
    elif cause == UNKNOWN:
        causal_status = UNDETERMINED
    else:
        causal_status = AGENT_CAUSED

    mechanism = _match(MECHANISM_RULES, text)
    if mechanism is None:
        if causal_status == ENVIRONMENT_CAUSED:
            mechanism = UNKNOWN
        elif cause == CAUSE_TIMEOUT:
            mechanism = MECH_RETRY_LOOP
        elif cause in (CAUSE_MISSING_FILE, CAUSE_ASSERTION):
            mechanism = MECH_NO_VERIFICATION
        else:
            mechanism = UNKNOWN

    return FailureSignature(cause, causal_status, mechanism)


def cluster_failures(outcomes: Sequence[CaseOutcome]) -> list[FailureCluster]:
    """Cluster failing outcomes by exact signature equality, largest first."""
    grouped: dict[str, list[CaseOutcome]] = {}
    signatures: dict[str, FailureSignature] = {}
    for outcome in outcomes:
        signature = classify(outcome)
        grouped.setdefault(signature.key, []).append(outcome)
        signatures[signature.key] = signature

    clusters = [
        FailureCluster(
            signature=signatures[key],
            case_ids=tuple(outcome.case_id for outcome in members),
            strata=tuple(sorted({outcome.stratum for outcome in members})),
            representative_message=next(
                (outcome.failure_message for outcome in members if outcome.failure_message),
                None,
            ),
        )
        for key, members in grouped.items()
    ]
    # Largest cluster first, then stable by key so ordering is reproducible.
    clusters.sort(key=lambda cluster: (-cluster.size, cluster.signature.key))
    return clusters


def cluster_split(result: SplitResult) -> list[FailureCluster]:
    """Cluster the failing outcomes of one split result."""
    return cluster_failures(result.failing_outcomes())


def signature_histogram(results: Sequence[SplitResult]) -> dict[str, int]:
    """Count signatures across split results, for before/after comparison."""
    counter: Counter[str] = Counter()
    for result in results:
        for outcome in result.failing_outcomes():
            counter[classify(outcome).key] += 1
    return dict(counter)
