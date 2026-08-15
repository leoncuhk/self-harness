"""Auditable community leaderboard for the FAB v2 public development set.

The module intentionally separates official-judge evidence from the local
numeric diagnostic. Public-27 is development data, so neither table is an
official Vals leaderboard or an estimate on a hidden population.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

PROTOCOL_ID = "fabv2-public27-dev-v1"
DATASET_SHA256 = "27b48c08a6099bc076b4194cac7cefe295082b9aedcbc67f4fedfa70468b427e"
VALID_TRACKS = ("reproduction", "open-harness", "oracle")
VALID_JUDGES = ("official", "numeric-diagnostic")
PUBLIC_QIDS = tuple(f"q{index:03d}" for index in range(1, 28))
_QID_PATTERN = re.compile(r"test-question-(q\d{3})$")


@dataclass(frozen=True)
class LeaderboardRow:
    """One validated, summarized community submission."""

    submission_id: str
    track: str
    model: str
    harness: str
    judge: str
    apparatus: str
    repeats: int
    score: float
    ci_low: float
    ci_high: float
    all_pass: float | None
    apparatus_rate: float
    eval_tokens: int | None
    search_tokens: int | None
    contamination: str
    eligible: bool
    ineligible_reason: str | None


def _content_hash(path: Path) -> str:
    """Hash the exact frozen variant rather than relying on a mutable label."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_numeric_submission(  # noqa: PLR0913 - explicit publication metadata
    run_dir: Path,
    *,
    submission_id: str,
    apparatus: str,
    contamination: str = "public-rubric-aware",
    track: str = "open-harness",
    variant_key: str = "baseline",
) -> dict[str, Any]:
    """Convert a complete controller run into a Public-27 diagnostic submission.

    Local artifacts can only establish the deterministic numeric diagnostic.  This
    exporter therefore cannot label evidence as an official FAB judge result.
    Missing outcomes are preserved as apparatus failures so the leaderboard
    validator excludes an incomplete matrix instead of silently dropping it.
    """
    manifest_path = run_dir / "manifest.json"
    variant_path = run_dir / "variants" / f"{variant_key}.json"
    if not manifest_path.is_file() or not variant_path.is_file():
        message = "run must contain manifest.json and the requested frozen variant"
        raise FileNotFoundError(message)
    manifest = json.loads(manifest_path.read_text())
    repeat_count = int(manifest.get("repeats", 0))
    if repeat_count < 1:
        message = "run manifest has no repetitions"
        raise ValueError(message)

    by_repeat: dict[int, dict[str, dict[str, Any]]] = {
        index: {} for index in range(repeat_count)
    }
    pattern = f"history/**/{variant_key}/rep*/cases/*"
    for case_dir in sorted(path for path in run_dir.glob(pattern) if path.is_dir()):
        match = _QID_PATTERN.search(case_dir.name)
        if not match:
            continue
        qid = match.group(1)
        repeat_name = case_dir.parents[1].name
        if not repeat_name.startswith("rep") or not repeat_name[3:].isdigit():
            continue
        repeat = int(repeat_name[3:])
        if repeat not in by_repeat or qid in by_repeat[repeat]:
            raise ValueError(f"duplicate {qid} in repeat {repeat}")
        summary_path = case_dir / "summary.json"
        runtime_path = case_dir / "run.json"
        if not summary_path.is_file() or not runtime_path.is_file():
            by_repeat[repeat][qid] = {
                "qid": qid,
                "status": "apparatus",
                "metrics": {},
                "tokens": None,
                "cost_usd": None,
                "latency_seconds": None,
            }
            continue
        summary = json.loads(summary_path.read_text())
        runtime = json.loads(runtime_path.read_text())
        metrics = summary.get("metrics") or {}
        score = summary.get("score")
        by_repeat[repeat][qid] = {
            "qid": qid,
            "status": "measured",
            "metrics": {
                "ungated_credit": metrics.get("ungated_credit"),
                "all_pass": bool(isinstance(score, int | float) and score >= 0.75),
            },
            "tokens": runtime.get("tokens"),
            "cost_usd": runtime.get("cost"),
            "latency_seconds": runtime.get("duration_s"),
        }

    runs = []
    for repeat, outcomes in sorted(by_repeat.items()):
        complete = []
        for qid in PUBLIC_QIDS:
            complete.append(
                outcomes.get(
                    qid,
                    {
                        "qid": qid,
                        "status": "apparatus",
                        "metrics": {},
                        "tokens": None,
                        "cost_usd": None,
                        "latency_seconds": None,
                    },
                )
            )
        runs.append({"seed": repeat, "outcomes": complete})

    search_tokens = 0
    for proposal_path in run_dir.glob("history/attempts/*/proposal.json"):
        try:
            proposal = json.loads(proposal_path.read_text())
        except (OSError, ValueError):
            continue
        usage = proposal.get("usage") or {}
        search_tokens += int(usage.get("total_tokens", 0) or 0)
    return {
        "submission_id": submission_id,
        "protocol_id": PROTOCOL_ID,
        "dataset_sha256": DATASET_SHA256,
        "track": track,
        "model": _require_string(manifest, "model"),
        "harness": f"sha256:{_content_hash(variant_path)}",
        "judge": "numeric-diagnostic",
        "apparatus": apparatus,
        "contamination": contamination,
        "search": {"tokens": search_tokens, "cost_usd": None, "wall_seconds": None},
        "runs": runs,
    }


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _metric_name(judge: str) -> str:
    return "partial_credit" if judge == "official" else "ungated_credit"


def _bootstrap_question_ci(
    per_question: dict[str, list[float]],
    *,
    samples: int = 10_000,
    seed: int = 0,
) -> tuple[float, float]:
    """Cluster-bootstrap questions, retaining repeats within each question."""
    qids = sorted(per_question)
    if not qids:
        return 0.0, 0.0
    values = {qid: mean(per_question[qid]) for qid in qids}
    rng = random.Random(seed)  # noqa: S311 - deterministic statistical resampling
    draws = sorted(
        mean(values[rng.choice(qids)] for _ in qids)
        for _ in range(samples)
    )
    return draws[int(samples * 0.025)], draws[min(samples - 1, int(samples * 0.975))]


def summarize_submission(payload: dict[str, Any]) -> LeaderboardRow:
    """Validate and summarize a submission without silently filling missing data."""
    submission_id = _require_string(payload, "submission_id")
    if payload.get("protocol_id") != PROTOCOL_ID:
        raise ValueError(f"{submission_id}: protocol_id must be {PROTOCOL_ID!r}")
    if payload.get("dataset_sha256") != DATASET_SHA256:
        raise ValueError(f"{submission_id}: dataset hash does not match the pinned Public-27 set")
    track = _require_string(payload, "track")
    if track not in VALID_TRACKS:
        raise ValueError(f"{submission_id}: invalid track {track!r}")
    judge = _require_string(payload, "judge")
    if judge not in VALID_JUDGES:
        raise ValueError(f"{submission_id}: invalid judge {judge!r}")
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError(f"{submission_id}: runs must be a non-empty list")

    metric_name = _metric_name(judge)
    per_question: dict[str, list[float]] = {qid: [] for qid in PUBLIC_QIDS}
    all_pass_values: list[float] = []
    attempted = 0
    apparatus_failures = 0
    eval_tokens = 0
    token_coverage = True
    structural_errors: list[str] = []
    for run_index, run in enumerate(runs):
        outcomes = run.get("outcomes") if isinstance(run, dict) else None
        if not isinstance(outcomes, list):
            raise TypeError(f"{submission_id}: run {run_index} outcomes must be a list")
        seen: set[str] = set()
        for outcome in outcomes:
            qid = _require_string(outcome, "qid")
            if qid not in per_question:
                structural_errors.append(f"unexpected {qid}")
                continue
            if qid in seen:
                structural_errors.append(f"duplicate {qid} in run {run_index}")
                continue
            seen.add(qid)
            attempted += 1
            if outcome.get("status") == "apparatus":
                apparatus_failures += 1
                continue
            metrics = outcome.get("metrics")
            value = metrics.get(metric_name) if isinstance(metrics, dict) else None
            if not isinstance(value, int | float) or not 0 <= float(value) <= 1:
                structural_errors.append(f"missing {metric_name} for {qid} in run {run_index}")
                continue
            per_question[qid].append(float(value))
            all_pass = metrics.get("all_pass")
            if isinstance(all_pass, bool | int | float):
                all_pass_values.append(float(all_pass))
            tokens = outcome.get("tokens")
            if isinstance(tokens, int) and tokens >= 0:
                eval_tokens += tokens
            else:
                token_coverage = False
        missing = set(PUBLIC_QIDS) - seen
        if missing:
            structural_errors.append(f"run {run_index} missing {len(missing)} questions")

    observed = [value for values in per_question.values() for value in values]
    score = mean(observed) if observed else 0.0
    ci_low, ci_high = _bootstrap_question_ci(
        {qid: values for qid, values in per_question.items() if values}
    )
    contamination = _require_string(payload, "contamination")
    reasons = list(structural_errors)
    if track == "oracle":
        reasons.append("oracle track is excluded from capability ranking")
    if len(runs) < 3:
        reasons.append("fewer than three complete repeats")
    if apparatus_failures:
        reasons.append(f"{apparatus_failures} apparatus failures")
    if len(observed) != len(runs) * len(PUBLIC_QIDS):
        reasons.append("incomplete scored outcome matrix")
    search = payload.get("search")
    search_tokens = search.get("tokens") if isinstance(search, dict) else None
    if not isinstance(search_tokens, int) or search_tokens < 0:
        search_tokens = None
    return LeaderboardRow(
        submission_id=submission_id,
        track=track,
        model=_require_string(payload, "model"),
        harness=_require_string(payload, "harness"),
        judge=judge,
        apparatus=_require_string(payload, "apparatus"),
        repeats=len(runs),
        score=score,
        ci_low=ci_low,
        ci_high=ci_high,
        all_pass=mean(all_pass_values) if all_pass_values else None,
        apparatus_rate=0.0 if attempted == 0 else apparatus_failures / attempted,
        eval_tokens=eval_tokens if token_coverage else None,
        search_tokens=search_tokens,
        contamination=contamination,
        eligible=not reasons,
        ineligible_reason="; ".join(dict.fromkeys(reasons)) or None,
    )


def load_submissions(paths: list[Path]) -> list[LeaderboardRow]:
    """Load submission documents, accepting one object or a list per file."""
    rows: list[LeaderboardRow] = []
    for path in paths:
        payload = json.loads(path.read_text())
        submissions = payload if isinstance(payload, list) else [payload]
        rows.extend(summarize_submission(item) for item in submissions)
    return rows


def _tokens(value: int | None) -> str:
    return "unreported" if value is None else f"{value:,}"


def render_markdown(rows: list[LeaderboardRow]) -> str:
    """Render separately ranked evidence tables plus excluded submissions."""
    lines = [
        "# FAB v2 Public-27 Development Leaderboard",
        "",
        "This is an unofficial development-set comparison, not the Vals FAB v2 leaderboard. ",
        "Public rubrics are known, so confidence intervals quantify run/question variation, ",
        "not generalization to Vals' private test set.",
    ]
    for judge, title in (
        ("official", "Official-judge evidence"),
        ("numeric-diagnostic", "Local numeric diagnostic"),
    ):
        lines.extend(["", f"## {title}", ""])
        eligible = sorted(
            (row for row in rows if row.judge == judge and row.eligible),
            key=lambda row: (-row.score, row.eval_tokens if row.eval_tokens is not None else 10**30),
        )
        if not eligible:
            lines.append("No eligible submissions.")
            continue
        lines.extend(
            [
                "| Rank | Submission | Track | Model | Harness | Score (question-bootstrap 95% CI) | All-pass | Repeats | Apparatus | Eval tokens | Search tokens | Contamination |",
                "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | --- |",
            ]
        )
        for rank, row in enumerate(eligible, 1):
            all_pass = "unreported" if row.all_pass is None else f"{row.all_pass:.3f}"
            lines.append(
                f"| {rank} | `{row.submission_id}` | {row.track} | `{row.model}` | "
                f"`{row.harness}` | {row.score:.3f} [{row.ci_low:.3f}, {row.ci_high:.3f}] | "
                f"{all_pass} | {row.repeats} | `{row.apparatus}` | {_tokens(row.eval_tokens)} | "
                f"{_tokens(row.search_tokens)} | {row.contamination} |"
            )
    excluded = [row for row in rows if not row.eligible]
    lines.extend(["", "## Excluded or incomplete", ""])
    if not excluded:
        lines.append("None.")
    else:
        lines.extend(
            [
                "| Submission | Judge | Reason |",
                "| --- | --- | --- |",
                *(
                    f"| `{row.submission_id}` | {row.judge} | {row.ineligible_reason} |"
                    for row in excluded
                ),
            ]
        )
    lines.append("")
    return "\n".join(lines)
