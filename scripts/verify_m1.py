"""M1 strict verification — checks the VERIFY.md L1 pass criteria against a run dir.

Usage: uv run python runs/verify_m1.py runs/m1-smoke runs/m1-fixture/minimal_pytest.toml
Exit 0 = all criteria pass; exit 1 = any failure. Prints one line per criterion.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from better_harness.core import load_experiment


def main() -> int:
    run_dir = Path(sys.argv[1]).resolve()
    experiment = load_experiment(Path(sys.argv[2]).resolve())
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
        if not ok:
            failures.append(name)

    iter_dir = run_dir / "history" / "visible" / "iterations" / "001"
    workspace = iter_dir / "proposer_workspace"

    # 1. Surfaces actually rewritten by the model (diff vs baseline values).
    changed = []
    for name, surface in experiment.surfaces.items():
        path = workspace / "current" / surface.filename
        if path.exists() and path.read_text().strip() != surface.base_value.strip():
            changed.append(name)
    check("surfaces rewritten by model", bool(changed), f"changed={changed}")

    # 2. Prediction block parsed into the ledger.
    ledger = json.loads((run_dir / "ledger.json").read_text())
    entry = ledger["entries"][0]
    check(
        "prediction_made in ledger",
        entry.get("prediction_made") is True,
        f"predictions_made={ledger['summary'].get('predictions_made')}",
    )

    # 3. decision.json carries a real gate block with deltas.
    decision = json.loads((iter_dir / "decision.json").read_text())
    gate = decision.get("gate") or {}
    check(
        "gate block with real deltas",
        gate.get("gate") == "conservative" and "delta_in" in gate and "delta_ho" in gate,
        f"gate={gate.get('gate')} d_in={gate.get('delta_in')} d_ho={gate.get('delta_ho')}",
    )

    # 4. No undeclared_surface guard violations (wiring correctness).
    guard = decision.get("guard") or {}
    kinds = [violation.get("kind") for violation in guard.get("violations", [])]
    check("no undeclared_surface violations", "undeclared_surface" not in kinds, f"kinds={kinds}")

    # 5. Token accounting: usage metadata visible in the outer-agent result.
    result_path = workspace / "outer_agent_result.json"
    usage_found = False
    total_tokens = None
    if result_path.exists():
        blob = result_path.read_text()
        usage_found = "usage_metadata" in blob or "total_tokens" in blob
        try:
            payload = json.loads(blob)
            for message in payload.get("result", {}).get("messages", []):
                usage = message.get("usage_metadata") if isinstance(message, dict) else None
                if usage and usage.get("total_tokens"):
                    total_tokens = (total_tokens or 0) + int(usage["total_tokens"])
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    check("proposer token usage recorded", usage_found, f"total_tokens={total_tokens}")

    # 6. Proposal narrative exists.
    proposal = workspace / "proposal.md"
    check("proposal.md written", proposal.exists() and len(proposal.read_text()) > 50)

    print()
    print(f"M1: {'ALL CRITERIA PASS' if not failures else 'FAILED: ' + ', '.join(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
