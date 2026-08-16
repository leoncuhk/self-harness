#!/usr/bin/env bash
# Load the trusted local credential file with export semantics, then delegate.
# Values are never printed or copied into a command-line argument.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${repo_root}/.env"

if [[ -f "${env_file}" ]]; then
  set -a
  # shellcheck disable=SC1090 -- repository-local path resolved above
  source "${env_file}"
  set +a
fi

cd "${repo_root}"
exec uv run self-harness "$@"
