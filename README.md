# Self-Harness

An eval-driven system that improves the development harness around a fixed
coding agent. The optimizer may edit declared prompts, skills, tools, workflow,
memory policy, and middleware; it may not edit the goal, evaluator, task splits,
budgets, promotion rule, or audit evidence.

The repository implements two causally separate loops:

```text
inner: task -> coding agent + harness -> disposable product diff -> frozen CI
outer: traces -> diagnosis -> candidate harness -> inner-loop replay -> promotion
```

“Best” always means the best validated candidate found within the declared
budget. It does not mean a global optimum.

## What is implemented

- immutable goal contracts with continuous objectives and hard constraints;
- private run-local harness snapshots for concurrent, attributable evaluation;
- disposable product workspaces and CI executed outside the coding agent;
- train, adaptive-validation (`holdout`), and one-shot locked-test (`scorecard`) splits;
- trace-grounded failure signatures and 1–K bounded candidate proposals;
- static anti-leak, syntax, path, and surface-growth guards;
- no-regression, objective, latency, token, and cost gates;
- candidate lineage, accepted/rejected evidence, predictions, and an anytime leaderboard;
- explicit apparatus-failure classification and independent artifact auditing;
- Pytest, Harbor, and generic command-based coding-project runners.

See [architecture](docs/system/architecture.md),
[verification ladder](docs/evaluation/verification.md),
[field synthesis](docs/concepts/overview.md), and the
[bounded FAB v2 result](docs/evaluation/fabv2-case-study.md)
before interpreting an experiment.

The [ZCodeProject/Public-27 audit](docs/evaluation/fabv2-zcode-audit.md) records what was
integrated, what remains contaminated or unverified, and the evidence required
for an unofficial community comparison.

## Quick start

Requirements: Python 3.12+, `uv`, and credentials for the models used by a live
experiment.

```bash
uv sync --extra dev
uv run self-harness validate configs/coding_demo.toml
uv run pytest -q
uv run ruff check better_harness tests scripts
```

The deterministic coding fixture proves both loops without model spend:

```bash
uv run pytest -q tests/test_coding_runner.py::test_outer_loop_improves_the_coding_harness_and_inner_product
```

Run a declared experiment:

```bash
uv run self-harness inventory configs/coding_demo.toml
uv run self-harness run configs/coding_demo.toml \
  --output-dir runs/coding-demo
```

Run outputs contain the frozen manifest, variant values, workspace snapshots,
per-case traces and diffs, split results, candidate decisions, archive, ledger,
and final report. `runs/` is intentionally ignored because it can contain large
or sensitive execution evidence.

## Promotion protocol

For each generation the outer agent sees only current surfaces, visible training
failures, and prior visible evidence. A proposed edit is promoted only when:

1. all static guards pass;
2. the primary objective improves by the configured minimum;
3. binary pass rate and declared constraints do not regress;
4. resource growth stays within its frozen ceiling;
5. both train and adaptive validation satisfy the gate.

The locked test is unavailable to the proposer and is read for the baseline and
final selected harness only. Because adaptive validation participates in every
selection, it is not called a truly untouched holdout in the architecture docs.

## Repository map

```text
better_harness/       optimization kernel and runner adapters
benchmarks/coding/    deterministic dual-loop product fixture
benchmarks/agentic/   generic agent fixture and deterministic verifiers
benchmarks/fabv2/     27-question public FAB development set and bounded case study
configs/              reproducible experiment contracts
docs/                 indexed design, research, evaluation, and development records
examples/             minimal runnable configuration examples
research/             isolated source snapshots and non-executable research archives
runs/                 ignored local raw evidence; only its retention policy is tracked
scripts/              artifact auditor and analysis utilities
tests/                unit, contract, resume, and end-to-end tests
```

The Python package retains the historical `better_harness` name for artifact
compatibility. `self-harness` is the preferred CLI.

## Evidence standard

A green test suite establishes orchestration correctness, not self-improvement.
A credible efficacy claim additionally needs non-degenerate baseline headroom,
replicated train/validation gain, one-shot locked-test gain, equal-budget retry
or refinement comparators, and ideally transfer to new projects or models. The
small FAB v2 study is an integration case study, not a competition-wide result.

Before citing any run:

```bash
uv run python scripts/verify_artifacts.py runs/<run-name>
```

## Safety boundary

Workspace surfaces are copied into private run directories and path traversal is
rejected. This protects causal attribution and the source workspace. It is not a
complete hostile-code sandbox: live coding agents and benchmark tools should
still run inside an OS/container sandbox with least-privilege credentials and
network policy appropriate to the project.

## Acknowledgements

The design builds on Self-Harness, Agentic Harness Engineering, Meta-Harness,
Deep Agents harness engineering, and the broader autoresearch/evolution family.
The project began as a fork of LangChain's `better-harness` example; upstream
API names are retained where doing so preserves old experiments.
