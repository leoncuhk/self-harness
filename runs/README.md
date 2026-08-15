# Local run evidence

This directory is the canonical local home for raw experiment outputs. Its
contents may include model responses, traces, copied workspaces, evaluator
artifacts, costs, and unpublished results, so everything except this policy is
ignored by Git.

Retention policy:

- preserve manifests, reports, ledgers, decisions, answers, judge output,
  normalized traces, and source diffs for every cited run;
- caches, virtual environments, bytecode, and `_runtime/` package copies are
  rebuildable and may be removed;
- do not silently overwrite or combine runs with different manifest
  fingerprints;
- audit a run with `uv run python scripts/verify_artifacts.py runs/<name>`
  before using it as evidence;
- publish only reviewed, redacted artifacts. Never assume this directory is
  safe to commit wholesale.

Retain only runs cited by current documentation and verified by the independent
artifact audit. Superseded prototypes, invalidated runs, launcher logs, and
rebuildable runtime copies should be removed after their lessons are captured in
tests or architecture decisions.
