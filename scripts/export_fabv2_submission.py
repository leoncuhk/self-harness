"""Export an audited controller run to the unofficial Public-27 schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from self_harness.fabv2_leaderboard import export_numeric_submission


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--submission-id", required=True)
    parser.add_argument("--apparatus", default="free-reproduction-v1")
    parser.add_argument("--track", default="open-harness")
    parser.add_argument("--variant", default="baseline")
    args = parser.parse_args()
    payload = export_numeric_submission(
        args.run_dir,
        submission_id=args.submission_id,
        apparatus=args.apparatus,
        track=args.track,
        variant_key=args.variant,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
