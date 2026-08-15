#!/usr/bin/env python3
"""Recompute FAB diagnostic aggregates directly from per-case judge artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_verdicts(run: Path) -> list[dict]:
    """Load the baseline verdict for each unique public question in a run."""
    verdicts: dict[str, dict] = {}
    for path in sorted(run.rglob("judge.json")):
        if "/baseline/" not in path.as_posix():
            continue
        payload = json.loads(path.read_text())
        payload["_path"] = str(path)
        qid = str(payload["qid"])
        if qid in verdicts:
            raise ValueError(f"duplicate baseline verdict for {qid} in {run}")
        verdicts[qid] = payload
    if not verdicts:
        raise ValueError(f"no baseline judge artifacts found in {run}")
    return [verdicts[qid] for qid in sorted(verdicts)]


def summarize(verdicts: list[dict]) -> dict[str, float | int]:
    """Return explicitly named macro and global-weighted aggregates."""
    known = [
        criterion
        for verdict in verdicts
        for criterion in verdict["criteria"]
        if criterion["passed"] is not None
    ]
    nonempty = 0
    for verdict in verdicts:
        answer_path = Path(verdict["_path"]).with_name("answer.txt")
        nonempty += int(answer_path.exists() and bool(answer_path.read_text().strip()))
    return {
        "questions": len(verdicts),
        "question_mean_ungated": sum(float(v["ungated_credit"]) for v in verdicts)
        / len(verdicts),
        "question_mean_partial": sum(float(v["partial_credit"]) for v in verdicts)
        / len(verdicts),
        "global_severity_weighted_credit": sum(
            float(criterion["severity"]) * bool(criterion["passed"])
            for criterion in known
        )
        / sum(float(criterion["severity"]) for criterion in known),
        "nonempty_answers": nonempty,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", type=Path)
    args = parser.parse_args()
    for run in args.runs:
        verdicts = load_verdicts(run)
        result = summarize(verdicts)
        print(f"{run}:")
        for key, value in result.items():
            rendered = f"{value:.6f}" if isinstance(value, float) else str(value)
            print(f"  {key}: {rendered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
