#!/bin/zsh
# Launch a better-harness stage detached, with credentials from .env (never inline).
# Usage: scripts/run_stage.sh <config.toml> <output-dir> <max-iterations> <repeats> <marker>
# Example: scripts/run_stage.sh configs/mvp2_agentic.toml runs/mvp2-b1 0 9 MVP2_B1
set -eu
REPO="$(cd "$(dirname "$0")/.." && pwd)"
source "$REPO/.env"
export OPENAI_API_KEY OPENAI_BASE_URL
cd "$REPO"
# caffeinate -is: block idle/system sleep for the duration — laptop sleep
# severs in-flight API calls and has killed multi-hour runs three times.
caffeinate -is uv run better-harness run "$1" --output-dir "$2" --max-iterations "$3" --repeats "$4"
echo "${5}_DONE exit=$?"
