# Design: the fork, the rigor layer, and the evaluation methodology

Fork of `examples/better-harness` from
[langchain-ai/deepagents](https://github.com/langchain-ai/deepagents) @ `6a5d93f`
(2026-08-08). Upstream ships the plumbing (declarative editable surfaces, a
train/holdout/scorecard split with the private splits hidden from the outer agent,
pytest and Harbor runners, per-iteration decision artifacts). It does not ship the
experimental rigor that decides whether any number coming out of the loop means
anything. This fork adds that layer — everything additive, no upstream file
rewritten, so rebases stay cheap.

## Editable surfaces and the read-only boundary

Editable (declared per-experiment in TOML): system prompt, tools, skills,
middleware — arbitrary `workspace_file` / `module_attr` surfaces. **Never editable:**
the evaluator and its tests, case ids and task literals, model/compute knobs
(model=, temperature, token/reasoning budgets), the gate, the runners. The guard
(P1-3) enforces the cheap-to-check part of this statically; the rest is protocol.

## The six patches

| Patch | Problem it kills | Mechanism |
| --- | --- | --- |
| **P0-1 repeats** (`repeats.py`) | single-rollout noise promoted as signal | every split runs `repeats`× (default 3); counts are attempts, so correctness is pass@1; per-case status passed/failed/**flaky**; a flaky case never reads as a win; evidence points at a genuinely failing repeat; `repeats=1` reproduces upstream exactly |
| **P0-2 gate** (`gate.py`) | upstream's combined sum lets a candidate rob holdout to pay train | conservative rule `Δ_in≥0 ∧ Δ_ho≥0 ∧ max(Δ_in,Δ_ho)>0`; `gate="combined"` kept for A/B |
| **P1-3 guard** (`guards.py`) | memorising case ids, buying compute, touching the verifier, growing until something sticks | static check before any eval is spent; kinds: `case_id_leak` (scans all splits), `forbidden_pattern`, `surface_bloat` (ratio **and** absolute floor — a ratio alone is meaningless against a 78-byte seed), `undeclared_surface`; not a sandbox, and says so |
| **P1-4 cost veto** (`cost.py`) | buying pass rate with 3× tool calls | budget check after the gate; tokens/cost read post-hoc from runner `summary.json`; unmeasured spend reports `None`, never zero; latency veto only past an absolute floor (wall-clock ratios below it are machine noise) |
| **P2-5 signatures + K** (`signatures.py`) | untargeted proposals; infra noise mined as harness weakness | failure signature φ(r)=(cause, causal status, mechanism), clustered by exact triple equality; environment failures classify `environment_caused` and are excluded; flaky gets its own signature (needs stabilisation, not a fix); K candidates round-robin across clusters, at most one promoted (largest holdout gain) |
| **P2-6 ledger** (`ledger.py`) | an edit with no prediction cannot be wrong | proposal must end with a fenced JSON block: root_cause / evidence / flip_to_pass / at_risk; graded after eval: precision, recall, unexpected passes, and **unpredicted regressions**; pass rate says the loop improves, prediction accuracy says whether it *understands why* |

Surface changes: `[experiment] repeats/gate/candidates`, `[guards]`, `[budget]`
config sections; CLI `--repeats/--gate`; `decision.json` carries gate/guard/budget/
cost/prediction blocks; run root gains `ledger.json` + `ledger.md`.

Known limits (unchanged from the fork notes): no process isolation; signature rules
are text heuristics (watch the `unknown` rate); the gate is Δ≥0 over attempts, not a
paired significance test (analysis scripts add bootstrap CIs on top); scorecard
access discipline is protocol, not code.

One further limit, larger than any of the above and identified against the 2026
literature: **the proposer never sees an execution trace.** Inner-agent
trajectories are discarded after each rollout, so φ(r) is computed from pytest
assertion text rather than from behaviour, and box ② is pattern-matching error
strings. Every published positive result in this area feeds traces to its
proposer. Full gap list and build order: [roadmap.md](roadmap.md).

## Evaluation methodology

**Three-way split.** `train` visible to the proposer; `holdout` scored but never
shown (drives promotion); `scorecard` run at baseline and final only, and *read*
exactly once per pre-registration, after the decisive comparison.

**Baseline family:**

| | What it isolates |
| --- | --- |
| B0 | seed harness, pass@1 |
| **B1** | seed harness, best-of-N at equal spend — **the decisive comparison**; evolution that can't beat it adds nothing over retries |
| B5 | mature harness (stock deepagents prompt), zero evolution — the honest starting point every published result omits |

**Metrics beyond pass rate:** prediction precision vs base rate, unpredicted
regressions, signature `unknown` rate, guard rejection kinds, gain concentration,
cost per case, updater×beneficiary transfer matrix (L5).

**Statistical floor:** bootstrap CI over cases (`scripts/mvp_analysis.py`); a delta
smaller than the baseline CI half-width is unreadable, and the pre-registered
headroom window ([0.20, 0.85] combined baseline) refuses to run evolution on a
saturated or floored testbed.

## The agentic suite (`benchmarks/agentic/`)

16 authored tasks, 4 strata (extraction / format / multistep / robustness),
deterministic 2/1/1 split per stratum → 8 train / 4 holdout / 4 scorecard.
Real inner agent: `workspace/agent_harness.py` (frozen infra) loads the four
editable surfaces at call time, builds a deepagents agent over a per-task
`FilesystemBackend` sandbox, `temperature=0`, recursion limit 60, and reports
per-rollout tokens and `system_fingerprint`s into the eval summary. Verifiers
recompute expected values from task inputs by reference implementations — answers
are never stored where the agent could read them.

Known biases, disclosed in the [results](results.md): task-designer = experiment-runner;
train failure messages contain expected values (bounded by holdout-based decisions);
zero external comparability. Terminal-Bench 2.1 via harbor remains the confirmatory
step for external validity.

## Risk register (top entries)

| Risk | Mitigation |
| --- | --- |
| Evaluator not frozen (LLM judges) | deterministic verifiers only, no LLM judge anywhere |
| Provider model drift behind the proxy | per-rollout `system_fingerprint` capture; mid-stage change invalidates the stage |
| Equal-budget comparison silently fake | token accounting verified before spending (M1); writeup states token- vs rollout-matched |
| Testbed saturation / floor | pre-registered headroom window with a hard stop |
| Experimenter degrees of freedom | pre-registration registry ([mvp.md](mvp.md)): criteria frozen before data, bounded revisions, one scorecard unseal |
