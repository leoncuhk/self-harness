"""Analysis helpers for the MVP stages (M2 baseline stats, M4 pass@N and tokens).

Scorecard discipline: nothing here reads scorecard outputs unless
--include-scorecard is passed explicitly (permitted once, after the M4 decision).

Usage:
  uv run python scripts/mvp_analysis.py baseline-stats <run_dir> [--include-scorecard]
  uv run python scripts/mvp_analysis.py pass-at-n <run_dir>
  uv run python scripts/mvp_analysis.py tokens <run_dir> [--include-scorecard]
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

BOOTSTRAP_SEED = 20260811
BOOTSTRAP_ITERS = 10_000

SPLIT_DIRS = {
    "train": ("visible", "train"),
    "holdout": ("private", "holdout"),
    "scorecard": ("private", "scorecard"),
}


def _splits(include_scorecard: bool) -> list[str]:
    return ["train", "holdout", "scorecard"] if include_scorecard else ["train", "holdout"]


def _split_dir(run_dir: Path, split: str, variant: str) -> Path:
    visibility, name = SPLIT_DIRS[split]
    return run_dir / "history" / visibility / name / variant


def _load_repeats(run_dir: Path, split: str, variant: str) -> dict | None:
    path = _split_dir(run_dir, split, variant) / "repeats.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _case_fractions(run_dir: Path, split: str, variant: str) -> dict[str, float]:
    """Per-case pass fraction over repeats; falls back to result.json at repeats=1."""
    repeats = _load_repeats(run_dir, split, variant)
    if repeats is not None:
        return {case["case_id"]: float(case["pass_fraction"]) for case in repeats["cases"]}
    result = json.loads((_split_dir(run_dir, split, variant) / "result.json").read_text())
    return {
        outcome["case_id"]: 1.0 if outcome["status"] == "passed" else 0.0
        for outcome in result["outcomes"]
    }


def bootstrap_ci(values: list[float]) -> tuple[float, float, float]:
    """Percentile bootstrap over cases: (mean, lo95, hi95)."""
    rng = random.Random(BOOTSTRAP_SEED)
    mean = sum(values) / len(values)
    samples = []
    for _ in range(BOOTSTRAP_ITERS):
        draw = [values[rng.randrange(len(values))] for _ in values]
        samples.append(sum(draw) / len(draw))
    samples.sort()
    lo = samples[int(0.025 * BOOTSTRAP_ITERS)]
    hi = samples[int(0.975 * BOOTSTRAP_ITERS)]
    return mean, lo, hi


def cmd_baseline_stats(run_dir: Path, include_scorecard: bool) -> None:
    for split in _splits(include_scorecard):
        fractions = _case_fractions(run_dir, split, "baseline")
        values = list(fractions.values())
        mean, lo, hi = bootstrap_ci(values)
        flaky = [case for case, frac in fractions.items() if 0.0 < frac < 1.0]
        print(f"[{split}] baseline pass@1 = {mean:.3f}  CI95 = [{lo:.3f}, {hi:.3f}]  "
              f"half-width = {(hi - lo) / 2:.3f}")
        print(f"[{split}] flaky cases: {len(flaky)}/{len(values)}"
              + (f" -> {flaky}" if flaky else ""))
        for case, frac in sorted(fractions.items()):
            print(f"    {frac:>5.2f}  {case}")


def cmd_pass_at_n(run_dir: Path) -> None:
    for split in ("train", "holdout"):
        repeats = _load_repeats(run_dir, split, "baseline")
        if repeats is None:
            print(f"[{split}] no repeats.json — pass@N needs repeats > 1")
            continue
        n = repeats["repeats"]
        cases = repeats["cases"]
        hits = sum(1 for case in cases if float(case["pass_fraction"]) > 0.0)
        print(f"[{split}] pass@{n} = {hits}/{len(cases)} = {hits / len(cases):.3f}")
        for case in sorted(cases, key=lambda c: c["case_id"]):
            print(f"    {'PASS' if float(case['pass_fraction']) > 0 else 'fail'}  "
                  f"{case['pass_fraction']:>5.2f}  {case['case_id']}")


def _sum_case_tokens(variant_dir: Path) -> int:
    total = 0
    for summary in variant_dir.rglob("summary.json"):
        try:
            payload = json.loads(summary.read_text())
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("total_tokens") is not None:
            total += int(payload["total_tokens"])
    return total


def _proposer_tokens(run_dir: Path) -> int:
    total = 0
    iterations = run_dir / "history" / "visible" / "iterations"
    if not iterations.exists():
        return 0
    for result in iterations.rglob("outer_agent_result.json"):
        blob = result.read_text()
        try:
            payload = json.loads(blob)
        except json.JSONDecodeError:
            continue
        for message in payload.get("result", {}).get("messages", []):
            if isinstance(message, dict):
                usage = message.get("usage_metadata") or {}
                if usage.get("total_tokens"):
                    total += int(usage["total_tokens"])
    return total


def cmd_tokens(run_dir: Path, include_scorecard: bool) -> None:
    grand = 0
    for split in _splits(include_scorecard):
        visibility, name = SPLIT_DIRS[split]
        split_root = run_dir / "history" / visibility / name
        if not split_root.exists():
            continue
        for variant_dir in sorted(split_root.iterdir()):
            if not variant_dir.is_dir():
                continue
            tokens = _sum_case_tokens(variant_dir)
            grand += tokens
            print(f"[{split}] {variant_dir.name}: {tokens:,} tokens")
    proposer = _proposer_tokens(run_dir)
    grand += proposer
    print(f"[proposer] {proposer:,} tokens")
    print(f"[total] {grand:,} tokens" + ("" if include_scorecard else " (scorecard excluded)"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["baseline-stats", "pass-at-n", "tokens"])
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--include-scorecard", action="store_true")
    args = parser.parse_args()
    if args.command == "baseline-stats":
        cmd_baseline_stats(args.run_dir, args.include_scorecard)
    elif args.command == "pass-at-n":
        cmd_pass_at_n(args.run_dir)
    else:
        cmd_tokens(args.run_dir, args.include_scorecard)


if __name__ == "__main__":
    main()
