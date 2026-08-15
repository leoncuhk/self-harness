"""Build the unofficial FAB v2 Public-27 development leaderboard."""

from __future__ import annotations

import argparse
from pathlib import Path

from better_harness.fabv2_leaderboard import load_submissions, render_markdown


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("submissions", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = load_submissions(args.submissions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
