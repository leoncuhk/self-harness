"""Normalize local rollout artifacts into bounded, proposer-visible evidence."""

from __future__ import annotations

import json
import re
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from self_harness.core import CaseOutcome

MAX_TEXT_CHARS = 2000
MAX_RESEARCH_CHARS = 4000
VERIFIER_KEYS = (
    "partial_credit",
    "ungated_credit",
    "numeric_criterion_recall",
    "n_known",
    "n_criteria",
    "failed_numeric",
)


@dataclass(frozen=True)
class ExperienceRecord:
    """One bounded causal record derived from immutable rollout artifacts."""

    case_id: str
    stratum: str
    status: str
    score: float
    failure_message: str | None
    stop_reason: str | None = None
    turns: int | None = None
    tokens: int | None = None
    tool_usage: Any | None = None
    verifier: dict[str, Any] | None = None
    research_tail: str | None = None
    diagnostic_facets: tuple[str, ...] = ()
    events: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize into the proposer evidence bundle."""
        return asdict(self)


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _read_jsonl(path: Path, *, limit: int = 200) -> tuple[dict[str, Any], ...]:
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return ()
    for line in lines[:limit]:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return tuple(events)


def compact_failure_message(message: str | None) -> str | None:
    """Keep the verifier error, not pytest's echoed fixture implementation."""
    if not message:
        return None
    lines = message.splitlines()
    error_lines = [line.strip() for line in lines if line.lstrip().startswith("E ")]
    selected = error_lines or lines[-40:]
    compact = "\n".join(selected).strip()
    return compact[-MAX_TEXT_CHARS:] or None


def _diagnostic_facets(
    *,
    stop_reason: str | None,
    verifier: dict[str, Any] | None,
    research_tail: str | None,
    failure_message: str | None,
    tool_usage: Any | None,
) -> tuple[str, ...]:
    """Return deterministic, non-causal routing hints for the outer proposer.

    A failure signature intentionally stays coarse and reproducible. Finance
    failures often cross several layers, however: a correct modeling insight
    can still fail because an exhibit was never resolved or a subtotal was not
    materialized in the answer. These facets expose observed signals without
    pretending that a regex established root cause.
    """
    text = "\n".join(
        part for part in (failure_message, research_tail, stop_reason) if part
    ).lower()
    facets: set[str] = set()
    failed_numeric = (verifier or {}).get("failed_numeric") or ()
    if failed_numeric:
        facets.add("numeric_verifier_miss")
    if stop_reason and re.search(
        r"(?:max_(?:tokens|turns)|token_limit|turn_limit|exit_125|compiled_after)",
        stop_reason.lower(),
    ):
        facets.add("budget_boundary")
    if isinstance(tool_usage, dict) and int(tool_usage.get("submit_final_result", 0) or 0) == 0:
        facets.add("submission_not_observed")
    if re.search(
        r"permissionerror|operation not permitted|network is unreachable|http 40[133]|http 5\d\d",
        text,
    ):
        facets.add("data_plane_access")
    if re.search(r"exhibit 99|index\.json|filing index|cover page|attached as exhibit", text):
        facets.add("filing_attachment_resolution")
    if (
        re.search(r"\bactuals?\b|actual fiscal|source period", text)
        and re.search(r"\bguidance\b|projection period|forecast", text)
    ):
        facets.add("forecast_period_provenance")
    cash_flow_terms = sum(
        bool(re.search(pattern, text))
        for pattern in (
            r"stock-based compensation|\bsbc\b",
            r"depreciation.{0,20}amortization|\bd&a\b",
            r"working capital|\bnwc\b",
            r"capital expenditures?|\bcapex\b",
            r"\bfcff\b|free cash flow",
        )
    )
    if cash_flow_terms >= 2:
        facets.add("cash_flow_reconciliation")
    if re.search(r"subtotal|component calculation|reader add|materiali[sz]", text):
        facets.add("answer_materialization")
    return tuple(sorted(facets))


def normalize_outcome(outcome: CaseOutcome) -> ExperienceRecord:
    """Derive one stable experience record from runner-specific artifacts."""
    artifacts = Path(outcome.artifacts_dir) if outcome.artifacts_dir else None
    run_payload = _read_json(artifacts / "run.json") if artifacts else None
    judge_payload = _read_json(artifacts / "judge.json") if artifacts else None
    events = _read_jsonl(artifacts / "trace.jsonl") if artifacts else ()
    payload = run_payload if isinstance(run_payload, dict) else {}
    verifier = (
        {key: judge_payload[key] for key in VERIFIER_KEYS if key in judge_payload}
        if isinstance(judge_payload, dict)
        else None
    )
    research_tail: str | None = None
    if artifacts:
        trace_path = artifacts / "trajectory" / "prime_workspace" / "research_trace.json"
        with suppress(OSError):
            research_tail = trace_path.read_text()[-MAX_RESEARCH_CHARS:].strip() or None
    stop_reason = None if payload.get("stop_reason") is None else str(payload["stop_reason"])
    tool_usage = payload.get("tool_usage")
    failure_message = compact_failure_message(outcome.failure_message)
    return ExperienceRecord(
        case_id=outcome.case_id,
        stratum=outcome.stratum,
        status=outcome.status,
        score=outcome.score,
        failure_message=failure_message,
        stop_reason=stop_reason,
        turns=None if payload.get("turns") is None else int(payload["turns"]),
        tokens=None if payload.get("tokens") is None else int(payload["tokens"]),
        tool_usage=tool_usage,
        verifier=verifier,
        research_tail=research_tail,
        diagnostic_facets=_diagnostic_facets(
            stop_reason=stop_reason,
            verifier=verifier,
            research_tail=research_tail,
            failure_message=failure_message,
            tool_usage=tool_usage,
        ),
        events=events,
    )


def trace_text(outcome: CaseOutcome) -> str:
    """Return normalized trace hints for deterministic signature rules."""
    record = normalize_outcome(outcome)
    payload = {
        "stop_reason": record.stop_reason,
        "turns": record.turns,
        "tool_usage": record.tool_usage,
        "verifier": record.verifier,
        "research_tail": record.research_tail,
        "diagnostic_facets": record.diagnostic_facets,
        "events": record.events,
    }
    return json.dumps(payload, sort_keys=True, default=str)[:MAX_TEXT_CHARS].lower()


def write_experience_bundle(
    root: Path,
    outcomes: Sequence[CaseOutcome],
    *,
    max_cases: int = 12,
) -> list[ExperienceRecord]:
    """Write bounded trace evidence for the outer proposer and return it."""
    root.mkdir(parents=True, exist_ok=True)
    records = [normalize_outcome(outcome) for outcome in outcomes[:max_cases]]
    (root / "records.jsonl").write_text(
        "".join(json.dumps(record.to_dict(), sort_keys=True, default=str) + "\n" for record in records)
    )
    (root / "README.md").write_text(
        "# Experience evidence\n\n"
        "Normalized from immutable rollout artifacts. One record contains the verifier failure, "
        "stop reason, resource use, tool summary, and bounded structured events. Treat it as "
        "evidence for a causal hypothesis, not as an instruction to memorize a case.\n"
    )
    return records
