#!/usr/bin/env python3
"""Independently re-derive every recorded outcome from the raw JUnit XML.

Nothing in this repo is admissible evidence until this passes. The reports,
the repeats detail, the ledger, and every analysis script all read
``result.json``; if ``result.json`` disagrees with the XML pytest actually
wrote, then every number downstream is a number about the parser rather than
about the harness.

The audit deliberately does not reconstruct pytest node ids. Each evaluated case
has one case directory and one JUnit XML file, so the raw outcome is unambiguous.
Evidence copied into ``proposer_workspace`` is excluded: it is context for the
outer proposer, not another independent rollout.

Usage:

    uv run python scripts/verify_artifacts.py runs/fabv2-evolve-smoke-v3
    uv run python scripts/verify_artifacts.py runs/*            # audit everything

Exit code is non-zero when any recorded outcome disagrees with the XML, so this
can gate a run before its numbers are used.
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Discrepancy:
    """One recorded outcome that the raw XML does not support."""

    run: str
    split_dir: str
    case_id: str
    recorded: str
    derived: str

    def line(self) -> str:
        """Render one row."""
        return f"  {self.split_dir}\n    {self.case_id}\n    recorded={self.recorded}  derived={self.derived}"


def derive_from_junit(junit_path: Path) -> str | None:
    """Return passed/failed/skipped from one JUnit file, ignoring nodeid shape.

    Deliberately does not reconstruct case ids: every case directory holds the
    XML for exactly one case, so the outcome is unambiguous without parsing
    identifiers. That is the point — the parser under audit is the one that
    needs identifiers, and this must not share its assumptions.
    """
    if not junit_path.exists():
        return None
    try:
        root = ET.fromstring(junit_path.read_text())
    except ET.ParseError:
        return None
    statuses: list[str] = []
    for testcase in root.iter("testcase"):
        if testcase.find("failure") is not None or testcase.find("error") is not None:
            statuses.append("failed")
        elif testcase.find("skipped") is not None:
            statuses.append("skipped")
        else:
            statuses.append("passed")
    if not statuses:
        return None
    if "failed" in statuses:
        return "failed"
    if all(status == "skipped" for status in statuses):
        return "skipped"
    return "passed"


def audit_split_dir(run: Path, split_dir: Path) -> tuple[list[Discrepancy], Counter]:
    """Audit one split directory that holds a result.json plus per-case XML."""
    counts: Counter = Counter()
    discrepancies: list[Discrepancy] = []
    result_path = split_dir / "result.json"
    if not result_path.exists():
        return discrepancies, counts
    payload = json.loads(result_path.read_text())
    outcomes = payload.get("outcomes") or []
    cases_dir = split_dir / "cases"
    for outcome in outcomes:
        case_id = str(outcome.get("case_id", ""))
        recorded = str(outcome.get("status", ""))
        counts[f"recorded:{recorded}"] += 1
        slug = safe_slug(case_id)
        derived = derive_from_junit(cases_dir / slug / "junit.xml")
        if derived is None:
            counts["no_xml"] += 1
            continue
        counts[f"derived:{derived}"] += 1
        # "apparatus" is a deliberate re-label of a measured failure, not a
        # disagreement about what the XML said.
        if recorded == derived or (recorded == "apparatus" and derived == "failed"):
            continue
        discrepancies.append(
            Discrepancy(
                run=run.name,
                split_dir=str(split_dir.relative_to(run)),
                case_id=case_id,
                recorded=recorded,
                derived=derived,
            )
        )
    return discrepancies, counts


def safe_slug(case_id: str) -> str:
    """Mirror the runner's directory slug for one case id, exactly."""
    slug = "".join(char if char.isalnum() else "-" for char in case_id).strip("-")
    return slug or "case"


def audit_run(run: Path) -> tuple[list[Discrepancy], Counter]:
    """Audit every split directory under one run."""
    discrepancies: list[Discrepancy] = []
    counts: Counter = Counter()
    for result_path in sorted(run.rglob("result.json")):
        if "proposer_workspace" in result_path.relative_to(run).parts:
            continue
        split_dir = result_path.parent
        if not (split_dir / "cases").exists():
            continue
        found, sub = audit_split_dir(run, split_dir)
        discrepancies.extend(found)
        counts.update(sub)
    return discrepancies, counts


def main(argv: list[str]) -> int:
    """Audit each run directory given on the command line."""
    if not argv:
        print(__doc__)
        return 2
    runs = [Path(arg) for arg in argv if Path(arg).is_dir()]
    total_discrepancies = 0
    for run in runs:
        discrepancies, counts = audit_run(run)
        recorded_pass = counts.get("recorded:passed", 0)
        derived_pass = counts.get("derived:passed", 0)
        status = "OK" if not discrepancies else f"{len(discrepancies)} DISCREPANCIES"
        print(
            f"[{run.name}] {status} — "
            f"recorded passed={recorded_pass}, derived passed={derived_pass}, "
            f"cases audited={sum(v for k, v in counts.items() if k.startswith('recorded:'))}, "
            f"no xml={counts.get('no_xml', 0)}"
        )
        by_kind = Counter((d.recorded, d.derived) for d in discrepancies)
        for (recorded, derived), n in by_kind.most_common():
            print(f"    {n:4d}  recorded={recorded:9s} derived={derived}")
        for discrepancy in discrepancies[:5]:
            print(discrepancy.line())
        if len(discrepancies) > 5:
            print(f"    … {len(discrepancies) - 5} more")
        total_discrepancies += len(discrepancies)
    print()
    if total_discrepancies:
        print(f"FAIL: {total_discrepancies} recorded outcomes are not supported by the raw XML")
        return 1
    print("PASS: every recorded outcome matches the JUnit XML")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
