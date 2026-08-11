#!/bin/zsh
# Launch a better-harness stage detached, with credentials from .env (never inline).
# Usage: scripts/run_stage.sh <config.toml> <output-dir> <max-iterations> <repeats> <marker> [extra args...]
# Example: scripts/run_stage.sh configs/mvp2_agentic.toml runs/mvp2-evolve 5 3 MVP2_M3 --resume
#
# No `set -e`: the whole point of the marker is that a crashed stage says so.
# Under `set -e` a failure exited before the echo, leaving a log that looks
# identical to a run still in progress — which is how three dead M3 attempts
# went unnoticed for hours.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
source "$REPO/.env"
export OPENAI_API_KEY OPENAI_BASE_URL
cd "$REPO"

CONFIG="$1"; OUTPUT_DIR="$2"; ITERATIONS="$3"; REPEATS="$4"; MARKER="$5"
shift 5

# caffeinate -is: block idle/system sleep for the duration — laptop sleep
# severs in-flight API calls and has killed multi-hour runs three times.
# Scorecard rows stay out of stdout unless --show-scorecard is passed through.
caffeinate -is uv run better-harness run "$CONFIG" \
  --output-dir "$OUTPUT_DIR" \
  --max-iterations "$ITERATIONS" \
  --repeats "$REPEATS" \
  "$@"
status=$?
echo "${MARKER}_DONE exit=${status}"
exit "${status}"
