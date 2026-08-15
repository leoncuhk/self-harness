"""Build the bounded FAB v2 comparison from persisted run evidence."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Arm:
    """Comparable train, validation, and locked-test measurements."""

    name: str
    splits: tuple[dict[str, Any], ...]
    changed_surfaces: tuple[str, ...]

    @property
    def total_tokens(self) -> int | None:
        values = [_split_tokens(split) for split in self.splits]
        if any(value is None for value in values):
            return None
        return sum(value for value in values if value is not None)

    @property
    def total_duration_s(self) -> float:
        return sum(
            float(outcome.get("duration_s", 0.0))
            for split in self.splits
            for outcome in split.get("outcomes", [])
        )


def _split_tokens(split: dict[str, Any]) -> int | None:
    total = 0
    measured = False
    for outcome in split.get("outcomes", []):
        artifacts = outcome.get("artifacts_dir")
        if not artifacts:
            continue
        summary = Path(artifacts) / "summary.json"
        if not summary.exists():
            continue
        value = json.loads(summary.read_text()).get("total_tokens")
        if isinstance(value, int | float):
            total += int(value)
            measured = True
    return total if measured else None


def _arm(report: dict[str, Any], *, name: str, stage: str) -> Arm:
    return Arm(
        name=name,
        splits=(
            report[f"{stage}_train"],
            report[f"{stage}_holdout"],
            report[f"{stage}_scorecard"],
        ),
        changed_surfaces=tuple(report[stage]["changed_surfaces"]),
    )


def _score(split: dict[str, Any]) -> str:
    return f"{float(split['score']):.3f} ({split['passed']}/{split['total']})"


def render(
    evolved: dict[str, Any],
    comparator: dict[str, Any],
    *,
    outer_search_tokens: int | None = None,
) -> str:
    """Render a single evidence table without inferring statistical significance."""
    arms = (
        _arm(evolved, name="Seed", stage="baseline"),
        _arm(comparator, name="Hand-engineered B5", stage="baseline"),
        _arm(evolved, name="Self-Harness final", stage="final"),
    )
    lines = [
        "# FAB v2 bounded case study",
        "",
        "All arms use the same model, one case per split, and the same eight-turn, "
        "360-second, 5,000-output-token-per-call limits.",
        "",
        "| Arm | Train score (pass) | Validation score (pass) | Locked-test score (pass) | Eval tokens | Search tokens | Wall time | Changed surfaces |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for index, arm in enumerate(arms):
        tokens = "unmeasured" if arm.total_tokens is None else f"{arm.total_tokens:,}"
        search = (
            "unmeasured"
            if index == 2 and outer_search_tokens is None
            else f"{outer_search_tokens:,}"
            if index == 2
            else "0"
        )
        surfaces = ", ".join(arm.changed_surfaces) or "none"
        lines.append(
            f"| {arm.name} | {_score(arm.splits[0])} | {_score(arm.splits[1])} | "
            f"{_score(arm.splits[2])} | {tokens} | {search} | "
            f"{arm.total_duration_s:.1f}s | {surfaces} |"
        )

    seed, _, final = arms
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            f"Validation score delta (final - seed): "
            f"{float(final.splits[1]['score']) - float(seed.splits[1]['score']):+.3f}.",
            f"Locked-test score delta (final - seed): "
            f"{float(final.splits[2]['score']) - float(seed.splits[2]['score']):+.3f}.",
            "",
            "This is a causal integration check with n=1 per split and one stochastic repeat. "
            "It cannot establish a competition-wide ranking, statistical significance, transfer, "
            "or a global optimum. A promoted candidate establishes only the best validated harness "
            "found in this frozen run budget.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    """Load two reports and write the comparison."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--evolved-run", type=Path, required=True)
    parser.add_argument("--b5-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evolved = json.loads((args.evolved_run / "report.json").read_text())
    comparator = json.loads((args.b5_run / "report.json").read_text())
    search_values: list[int] = []
    for path in (args.evolved_run / "history" / "visible" / "iterations").glob(
        "*/proposer_workspace/outer_agent_result.json"
    ):
        value = json.loads(path.read_text()).get("usage", {}).get("total_tokens")
        if isinstance(value, int):
            search_values.append(value)
    outer_search_tokens = sum(search_values) if search_values else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(evolved, comparator, outer_search_tokens=outer_search_tokens))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
