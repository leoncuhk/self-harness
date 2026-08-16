# Self-Harness

An eval-driven system that improves the engineering harness around a fixed agent. It implements
two causally separate loops:

```text
product task ──> inner runtime ──> typed evidence + answer/code ──> frozen evaluator
                    ▲                                                 │
                    │ candidate harness                              │ visible train evidence
                    │                                                 ▼
             frozen controller <── outer proposer <── layer diagnosis
```

The Controller alone owns the goal, splits, evaluator, model, budgets, guards, archive, and
promotion decision. The proposer may change only declared harness surfaces. “Best” means the best
validated candidate found under one recorded contract and budget; it never means a global optimum
or an official FAB leaderboard result.

The repository currently proves three different things at different evidence levels:

- the deterministic coding fixture exercises both loops end to end without model spend;
- the FAB controller rejects invalid, duplicate, overfit, and non-improving candidates under frozen
  train/validation/scorecard contracts;
- one human-directed harness construction sequence now solves all four sampled hard FAB tasks with
  GPT-5.6-sol + Codex under one harness and data contract (4/4, each 1.0). This is a targeted
  diagnostic result, not an autonomous outer-loop win or an official leaderboard submission.

## Runtime adapters

- **Prime Agent is the current inner adapter** for FAB: persistent IPython state, evaluator-owned finance
  tools, optional `rlm(...)` specialists, evidence memory, verification, and a reserved compiler.
- **Pi is the current outer adapter**: one tool-free model call returns an atomic JSON candidate. This is
  intentionally smaller than a coding-agent loop because the Controller already provides bounded,
  normalized evidence. Invalid, partial, or undeclared edits are rejected before evaluation.
- **DeepAgents is not required.** It was useful background, but adds an unnecessary framework and
  dependency boundary to this implementation.

The architecture does not depend on any of these frameworks. Plain Python owns the causal control
plane; agent frameworks are replaceable execution adapters. Before search, the system distinguishes a weak
beneficiary model or broken data route from an evolvable orchestration, finance-semantics,
verification, or compiler failure. FAB candidates should pass typed source-period provenance,
calculation, invariant, and answer-manifest artifacts through that inner flow; external market data
must be frozen before a global promotion claim is credible. The included GTLS fixtures demonstrate
bounded, checksummed official-source snapshots for fragile historical facts; they do not imply that
the entire Public-27 source universe is already frozen.

Vertical behavior is supplied through a frozen declarative diagnostic contract. FAB owns its finance
layers and facets; the generic Controller and proposer prompt contain no finance-specific rules. A
new domain should add a runtime/artifact adapter, diagnostic profile, and frozen evaluator rather
than fork the optimization loop.

See [architecture](docs/system/architecture.md), [concepts](docs/concepts/overview.md), and the
[verification standard](docs/evaluation/verification.md).

## Quick start

Requirements: Python 3.12+, `uv`, Prime Agent for FAB inner runs, Pi for live outer proposals, and
credentials for the configured model route.

```bash
uv sync --extra dev
uv run self-harness validate configs/coding_demo.toml
uv run pytest -q
uv run ruff check .
```

The deterministic coding fixture proves both loops without model spend:

```bash
uv run pytest -q tests/test_coding_runner.py::test_outer_loop_improves_the_coding_harness_and_inner_product
```

FAB contracts:

```bash
# Inner-runtime integration only; no evolution claim
scripts/run_fabv2.sh run configs/fabv2_smoke.toml --output-dir runs/fabv2-smoke

# One train/validation/scorecard outer-loop mechanism check
scripts/run_fabv2.sh run configs/fabv2_evolve_smoke.toml \
  --output-dir runs/fabv2-evolve-smoke

# Public-27 8/8/8 development protocol
scripts/run_fabv2.sh run configs/fabv2.toml --output-dir runs/fabv2
```

The launcher exports values from the ignored local `.env` before starting subprocesses; plain
`source .env` does not export unmarked assignments. It does not print credentials.

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

## Current FAB conclusion

The latest autonomous Public-24 evolution evaluated six candidates and promoted none; the strong
human seed remains best under that frozen one-repeat DeepSeek+Prime contract. A later
human-directed, Codex-assisted diagnostic isolated q025's forecast-provenance and FCFF errors, then
exposed q013's separate historical-market-data and accounting-taxonomy failures.

The current unified strong harness combines the general fixes with evaluator-owned official SEC
snapshots for the fragile historical facts. Under one rubric-blind GPT-5.6-sol + Codex protocol it
scored q004=q013=q022=q025=1.0 (4/4). q013 also passed a separate fresh run at 1.0. On the critical
q025 control, removing the project harness while retaining the same model, tools, data, and budget
failed at gated 0.0 / ungated 0.6 and used roughly 1.19M input tokens versus the strong harness's
0.65M. This is evidence that the harness independently helps this sampled task; it is not evidence
that Pi autonomously discovered the final sequence.

These four public tasks were used for diagnosis, so the result is in-sample and cannot establish a
Public-27 optimum, cross-domain transfer, or leaderboard readiness. The official Vals score remains
unknown. Exact evidence and limitations are in the [FAB v2 case study](docs/evaluation/fabv2-case-study.md),
and the layered optimization decision is in [ADR 0003](docs/adr/0003-fab-layered-optimization.md).

Process and workspace isolation are not a hostile-code sandbox. Live agents still require an OS or
container boundary, least-privilege credentials, and an explicit network policy.

## Local data and publication safety

Raw `runs/`, caches, virtual environments, `.env`, and runtime copies are intentionally ignored.
They can exceed 10GB because every rollout preserves full events and a private data/cache snapshot;
none is required to install the package or clone the public repository. Publish only reviewed
summaries and redacted artifacts. Never commit model credentials, licensed validation questions, or
unreviewed traces, which may contain source text or model-provider metadata.

Self-Harness is available under the [Apache License 2.0](LICENSE). FAB public-development assets retain
their upstream terms and notices in [THIRD_PARTY_NOTICES.md](benchmarks/fabv2/THIRD_PARTY_NOTICES.md).
