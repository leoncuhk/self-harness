#!/usr/bin/env python3
"""Compare the frozen B0, B5, and Self-Harness arms of FAB Numeric-24 V5."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


@dataclass(frozen=True)
class Arm:
    """One frozen harness evaluated on all three V5 splits."""

    name: str
    train: dict[str, Any]
    holdout: dict[str, Any]
    scorecard: dict[str, Any]

    def metric(self, split: str, name: str) -> float:
        payload = getattr(self, split)
        value = payload.get("metrics", {}).get(name)
        if not isinstance(value, int | float):
            raise TypeError(f"{self.name} {split} did not measure {name}")
        return float(value)


def _load(run: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        json.loads((run / "manifest.json").read_text()),
        json.loads((run / "report.json").read_text()),
    )


def _fingerprints(arm: Arm) -> set[str | None]:
    return {
        arm.train.get("evaluation_fingerprint"),
        arm.holdout.get("evaluation_fingerprint"),
        arm.scorecard.get("evaluation_fingerprint"),
    }


def _execution_spend(run: Path) -> tuple[int, int | None]:
    """Return canonical inner rollouts and their fully recorded tokens."""
    records: list[Path] = []
    for root in (
        run / "history" / "visible" / "train",
        run / "history" / "private" / "holdout",
        run / "history" / "private" / "scorecard",
    ):
        if root.exists():
            records.extend(root.rglob("run.json"))
    total = 0
    complete = True
    for path in records:
        value = json.loads(path.read_text()).get("tokens")
        if isinstance(value, int) and value >= 0:
            total += value
        else:
            complete = False
    return len(records), total if complete else None


def _outer_tokens(run: Path) -> int | None:
    values: list[int] = []
    root = run / "history" / "visible" / "iterations"
    paths = [
        *root.glob("*/proposer_workspace/outer_agent_result.json"),
        *root.glob("*/proposer_workspace/k*/outer_agent_result.json"),
    ]
    for path in paths:
        value = json.loads(path.read_text()).get("usage", {}).get("total_tokens")
        if isinstance(value, int) and value >= 0:
            values.append(value)
    return sum(values) if values else None


def _oracle_retry(run: Path) -> tuple[int, float, float]:
    """Return repeats, oracle best-of-N diagnostic, and binary pass@N."""
    by_qid: dict[str, list[dict[str, Any]]] = {}
    for root in (
        run / "history" / "visible" / "train" / "baseline",
        run / "history" / "private" / "holdout" / "baseline",
        run / "history" / "private" / "scorecard" / "baseline",
    ):
        if not root.exists():
            continue
        for path in root.rglob("judge.json"):
            verdict = json.loads(path.read_text())
            by_qid.setdefault(str(verdict["qid"]), []).append(verdict)
    if not by_qid:
        msg = "retry run has no baseline judge artifacts"
        raise ValueError(msg)
    counts = {len(items) for items in by_qid.values()}
    if len(counts) != 1:
        msg = "retry run does not contain a complete question-by-repeat matrix"
        raise ValueError(msg)
    repeats = next(iter(counts))
    best = mean(max(float(item["ungated_credit"]) for item in items) for items in by_qid.values())
    pass_at_n = mean(
        any(float(item["partial_credit"]) >= 0.75 for item in items)
        for items in by_qid.values()
    )
    return repeats, best, pass_at_n


def render(*, evolved_run: Path, b5_run: Path, retry_run: Path | None = None) -> str:
    """Render a contract-checked comparison from persisted evidence."""
    evolved_manifest, evolved = _load(evolved_run)
    b5_manifest, b5 = _load(b5_run)
    metric = str(evolved_manifest["goal"]["primary_metric"])
    if b5_manifest["goal"]["primary_metric"] != metric:
        msg = "B5 and Self-Harness primary metrics differ"
        raise ValueError(msg)

    required = (
        "baseline_train",
        "baseline_holdout",
        "baseline_scorecard",
        "final_train",
        "final_holdout",
        "final_scorecard",
    )
    if any(evolved.get(key) is None for key in required):
        msg = "Self-Harness report is missing a frozen split"
        raise ValueError(msg)
    if any(b5.get(key) is None for key in required[:3]):
        msg = "B5 report is missing a frozen split"
        raise ValueError(msg)

    arms = (
        Arm("B0 official seed", evolved["baseline_train"], evolved["baseline_holdout"], evolved["baseline_scorecard"]),
        Arm("B5 hand-engineered", b5["baseline_train"], b5["baseline_holdout"], b5["baseline_scorecard"]),
        Arm("Self-Harness final", evolved["final_train"], evolved["final_holdout"], evolved["final_scorecard"]),
    )
    fingerprints = set().union(*(_fingerprints(arm) for arm in arms))
    if None in fingerprints or len(fingerprints) != 1:
        msg = "arms do not share one frozen evaluation fingerprint"
        raise ValueError(msg)

    evolved_rollouts, evolved_tokens = _execution_spend(evolved_run)
    b5_rollouts, b5_tokens = _execution_spend(b5_run)
    search_tokens = _outer_tokens(evolved_run)
    lines = [
        "# FAB v2 Numeric-24 V5 comparison",
        "",
        f"Frozen evaluation fingerprint: `{next(iter(fingerprints))}`.",
        f"Primary metric: `{metric}`. Public development evidence; not an official Vals score.",
        "",
        "| Arm | Train | Adaptive validation | Locked scorecard | Binary scorecard pass@1 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for arm in arms:
        lines.append(
            f"| {arm.name} | {arm.metric('train', metric):.4f} | "
            f"{arm.metric('holdout', metric):.4f} | {arm.metric('scorecard', metric):.4f} | "
            f"{float(arm.scorecard['correctness']):.4f} |"
        )

    seed, hand, final = arms
    holdout_delta = final.metric("holdout", metric) - seed.metric("holdout", metric)
    scorecard_delta = final.metric("scorecard", metric) - seed.metric("scorecard", metric)
    beats_b5 = final.metric("scorecard", metric) > hand.metric("scorecard", metric)
    lines.extend(
        [
            "",
            "## Evidence verdict",
            "",
            f"- Self-Harness validation delta over B0: `{holdout_delta:+.4f}`.",
            f"- Self-Harness locked-scorecard delta over B0: `{scorecard_delta:+.4f}`.",
            f"- Self-Harness beats B5 on locked scorecard: `{'yes' if beats_b5 else 'no'}`.",
            "- Equal-total-compute retry/Best-of-N: "
            f"`{'reported below' if retry_run is not None else 'not established by these two runs'}`.",
            "",
            "## Search and evaluation spend",
            "",
            "| Run | Inner rollouts | Inner tokens | Outer proposer tokens |",
            "| --- | ---: | ---: | ---: |",
            f"| Self-Harness campaign | {evolved_rollouts} | "
            f"{'unmeasured' if evolved_tokens is None else f'{evolved_tokens:,}'} | "
            f"{'unmeasured' if search_tokens is None else f'{search_tokens:,}'} |",
            f"| B5 fixed evaluation | {b5_rollouts} | "
            f"{'unmeasured' if b5_tokens is None else f'{b5_tokens:,}'} | 0 |",
            "",
            "A highest score in this table means only the best frozen harness among these "
            "three public-development arms. It is not a global optimum and is not an "
            "equal-search-budget result until the retry comparator is executed.",
            "",
        ]
    )
    if retry_run is not None:
        retry_rollouts, retry_tokens = _execution_spend(retry_run)
        retry_repeats, oracle_score, pass_at_n = _oracle_retry(retry_run)
        target_tokens = (
            None
            if evolved_tokens is None or search_tokens is None
            else evolved_tokens + search_tokens
        )
        ratio = (
            None
            if target_tokens is None or retry_tokens is None or target_tokens <= 0
            else retry_tokens / target_tokens
        )
        matched = ratio is not None and 0.9 <= ratio <= 1.1
        lines.extend(
            [
                "## Equal-compute retry upper bound",
                "",
                f"- B0 retries per question: `{retry_repeats}` ({retry_rollouts} rollouts).",
                f"- Oracle best-of-N `{metric}`: `{oracle_score:.4f}`.",
                f"- Binary pass@N: `{pass_at_n:.4f}`.",
                f"- Retry/evolution total-token ratio: "
                f"`{'unmeasured' if ratio is None else f'{ratio:.3f}x'}`.",
                f"- Equal-compute tolerance (0.9x-1.1x): `{'yes' if matched else 'no'}`.",
                "",
                "This is an oracle upper bound because the frozen evaluator chooses the best "
                "retry after seeing every answer. Beating it is stronger than beating a "
                "deployable selector; losing to it does not by itself prove deployment inferiority.",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evolved-run", required=True, type=Path)
    parser.add_argument("--b5-run", required=True, type=Path)
    parser.add_argument("--retry-run", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        render(
            evolved_run=args.evolved_run,
            b5_run=args.b5_run,
            retry_run=args.retry_run,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
