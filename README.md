# Self-Harness

An eval-driven system that improves the engineering harness around a fixed agent. It implements
two causally separate loops:

```text
product task ──> Prime inner runtime ──> answer or code change ──> frozen evaluator
                     ▲                                         │
                     │ candidate harness                       │ visible train evidence
                     │                                         ▼
              frozen controller <── atomic Pi proposer <── diagnostics
```

The Controller alone owns the goal, splits, evaluator, model, budgets, guards, archive, and
promotion decision. The proposer may change only declared harness surfaces. “Best” means the best
validated candidate found under one recorded contract and budget; it never means a global optimum
or an official FAB leaderboard result.

## Runtime choice

- **Prime Agent is the inner runtime** for FAB: persistent IPython state, evaluator-owned finance
  tools, optional `rlm(...)` specialists, evidence memory, verification, and a reserved compiler.
- **Pi is the outer proposer**: one tool-free model call returns an atomic JSON candidate. This is
  intentionally smaller than a coding-agent loop because the Controller already provides bounded,
  normalized evidence. Invalid, partial, or undeclared edits are rejected before evaluation.
- **DeepAgents is not required.** It was useful background, but adds an unnecessary framework and
  dependency boundary to this implementation.

See [architecture](docs/system/architecture.md), [concepts](docs/concepts/overview.md), and the
[verification standard](docs/evaluation/verification.md).

## Quick start

Requirements: Python 3.12+, `uv`, Prime Agent for FAB inner runs, Pi for live outer proposals, and
credentials for the configured model route.

```bash
uv sync --extra dev
uv run self-harness validate configs/coding_demo.toml
uv run pytest -q
uv run ruff check self_harness tests scripts
```

The deterministic coding fixture proves both loops without model spend:

```bash
uv run pytest -q tests/test_coding_runner.py::test_outer_loop_improves_the_coding_harness_and_inner_product
```

FAB contracts:

```bash
# Inner-runtime integration only; no evolution claim
uv run self-harness run configs/fabv2_smoke.toml --output-dir runs/fabv2-smoke

# One train/validation/scorecard outer-loop mechanism check
uv run self-harness run configs/fabv2_evolve_smoke.toml \
  --output-dir runs/fabv2-evolve-smoke

# Public-27 8/8/8 development protocol
uv run self-harness run configs/fabv2.toml --output-dir runs/fabv2
```

Use `configs/fabv2_minimal.toml` for the contract-matched minimal comparator. A credible efficacy
study must also run the strong zero-evolution baseline, evolved arm, and equal-total-token retry or
Best-of-N comparator with multiple repeats before opening the scorecard.

## Repository map

```text
self_harness/     frozen controller, gates, evidence, and runtime adapters
benchmarks/coding/  deterministic product-development dual-loop fixture
benchmarks/fabv2/   Public-27 data, Prime inner runtime, harnesses, frozen evaluator
configs/            executable experiment contracts
docs/               current concepts, architecture decisions, and evidence limits
scripts/            independent artifact audit and FAB leaderboard utilities
tests/              unit, contract, resume, and end-to-end verification
runs/               ignored local evidence; only its retention policy is tracked
```

Run artifacts contain the frozen manifest, private harness snapshots, per-case telemetry, candidate
decisions, prediction ledger, archive, and leaderboard. Audit any cited run independently:

```bash
uv run python scripts/verify_artifacts.py runs/<run-name>
```

Build the unofficial Public-27 community table from complete, protocol-conforming submissions:

```bash
uv run python scripts/build_fabv2_leaderboard.py submissions/*.json \
  --output leaderboard.md
```

Numeric-24 development runs and one-case smoke runs are deliberately ineligible for that table.

Process and workspace isolation are not a hostile-code sandbox. Live agents still require an OS or
container boundary, least-privilege credentials, and an explicit network policy.
