# Fork notes

Fork of `examples/better-harness` from
[langchain-ai/deepagents](https://github.com/langchain-ai/deepagents) @ `6a5d93f` (2026-08-08).

Upstream ships the plumbing that is genuinely annoying to build — declarative editable
surfaces, a three-way `train` / `holdout` / `scorecard` split with `holdout` and
`scorecard` hidden from the outer agent, pytest and Harbor runners, per-iteration
decision artifacts. What it does not ship is the experimental rigor that decides
whether any of the numbers coming out of the loop mean anything.

This fork adds that layer. Everything here is additive; no upstream file was rewritten,
so rebasing on upstream stays cheap.

## P0-1 — repeated evaluation

**Problem.** Upstream runs each candidate exactly once per split (`repeat`, `seed`,
`n_runs` and `trials` do not appear anywhere in the upstream tree). On a benchmark with
container flakiness or timeouts, run-to-run noise is routinely larger than the effect
being measured, so a single rollout makes accept/reject close to a coin flip. Noise gets
promoted into the main line and the loop then evolves on top of it.

**Change.** New `better_harness/repeats.py`. Every split runs `repeats` times
(default **3**) and the runs aggregate into one `SplitResult`:

- `passed` / `total` now count **attempts**, not cases, so `correctness` is a pass@1
  estimate over `n_cases × repeats`.
- Each case gets one aggregated outcome with `score` = pass fraction and a status of
  `passed` (every repeat), `failed` (no repeat), or `flaky` (mixed).
- `CaseOutcome.passed` stays `status == "passed"`, so `passing_case_ids()` keeps its
  "stably passing" meaning and a flaky case never reads as a win.
- The aggregated outcome points `artifacts_dir` / `failure_message` at a genuinely
  **failing** repeat when one exists, so the outer agent reads a real failure trace.
- Per-repeat detail lands in `repeats.json` next to the aggregated `result.json`.

The runners are untouched. Repeats are isolated by handing the runner a `_RepeatLayout`
proxy that rewrites only `split_dir` (`.../<split>/<variant>/repNN/`), so the variant
JSON and the shared `_runtime` sitecustomize are still written once.

`repeats = 1` restores the upstream directory layout and behaviour exactly.

## P0-2 — conservative promotion gate

**Problem.** Upstream promotes on the *combined* pass count
(`core.py`, previously `accepted = (train.passed + holdout.passed) > (current...)`).
A sum lets a candidate rob Peter to pay Paul: holdout −2 with train +3 nets +1 and is
promoted. That is the textbook shape of overfitting to the split the proposer can see.

**Change.** New `better_harness/gate.py` implementing the Self-Harness promotion rule
([arXiv:2606.09498](https://arxiv.org/abs/2606.09498)):

```
Δ_in >= 0  and  Δ_ho >= 0  and  max(Δ_in, Δ_ho) > 0
```

Neither split may regress, at least one must improve, and pure no-ops are rejected.
`gate = "combined"` reproduces upstream behaviour for A/B comparison.

Every decision records `Δ_in`, `Δ_ho` and their rate equivalents into
`decision.json` and `report.json`.

## Surface changes

| Where | Change |
| --- | --- |
| `[experiment]` config | new `repeats` (default 3), `gate` (default `conservative`), `candidates` (default 1) |
| `[guards]` config | new section: `enabled`, `max_growth`, `min_bloat_bytes`, `forbidden_patterns` |
| `[budget]` config | new section: `enabled`, `max_cost_growth`, `max_latency_growth`, `min_latency_s` |
| CLI | `run --repeats N`, `run --gate {conservative,combined}` |
| `validate` | prints repeats and gate |
| `report.md` | prints repeats and gate, and warns when repeats < 3 or gate is `combined` |
| `decision.json` | adds `holdout_*`, `gate`, `guard`, `budget`, `cost`, `prediction`, `target_cluster` |
| Split dirs | `<split>/<variant>/repNN/` plus aggregated `result.json` + `repeats.json` when repeats > 1 |
| Iteration dirs | `.../iterations/NNN/kNN/` when `candidates > 1` |
| Run root | new `ledger.json` and `ledger.md` |
| Proposer workspace | new `failure_clusters.json`; `task.md` names the target cluster; `proposal.md` ships a prediction template |

## Upstream tests

`test_run_end_to_end_pytest_demo` and `test_run_end_to_end_harbor_backend` asserted
absolute pass counts, which now scale with `repeats`. They assert
`n * report.repeats` and `correctness == 1.0` instead, so they exercise the repeat path
rather than pinning it to 1.

## P1-3 — static edit guard

**Problem.** Upstream constrains *which* surfaces may be edited but not *what* is written
into them, and its README is explicit that the visible/private split "is not a hard
sandbox boundary yet". The cheapest paths to a higher score are all open: hard-code the
eval's own case ids, edit the model or token or reasoning budget, point the harness at the
verifier, or grow the harness until something sticks.

**Change.** New `better_harness/guards.py` statically checks each candidate **before it
costs an evaluation**. Violation kinds: `case_id_leak`, `forbidden_pattern`,
`surface_bloat`, `undeclared_surface`. Case-id scanning covers every split — a holdout id
appearing at all would mean the private split leaked. Unchanged surfaces are skipped, so
the guard judges the proposer's edits rather than the seed it was handed.

Bloat requires **both** a ratio and an absolute floor (default 4 KB). A ratio alone is
meaningless against a small seed: the upstream demo baseline is 78 bytes, which exceeds
any multiplier the moment the proposer writes a real sentence.

The guard is not a sandbox. It cannot stop code from misbehaving at runtime; it closes the
cheap holes and makes every rejection auditable.

## P1-4 — cost veto

**Problem.** Gating on pass rate alone lets a candidate buy its improvement: add a
verification pass that triples the tool calls, widen a retry loop, split one step into
five. Pass rate rises, the gate approves, and the harness quietly costs an order of
magnitude more to run. LangChain's own "reasoning sandwich" result is exactly this shape
of trade, and upstream has no way to see it.

**Change.** New `better_harness/cost.py`. A candidate that clears the correctness gate is
still rejected if it exceeds the spend or latency budget. Collection needs no runner
changes: latency comes from `CaseOutcome.duration_s`, and tokens or dollars are read
post-hoc from the `summary.json` the runners already write, under configurable keys.

Two deliberate choices:

- Unmeasured spend is reported as `None`, never as zero. A budget you cannot measure must
  not read as a budget you are inside of; the reason string says `not enforced`.
- The latency veto only engages past an absolute floor (default 30 s total). Wall clock
  moves with machine load and container scheduling, so a ratio over sub-second runs is
  noise rather than a regression. Token or cost data is preferred whenever available.

## P2-5 — failure signatures and K candidates

**Change (signatures).** New `better_harness/signatures.py` implements `φ(r) = (c, q, m)`
— terminal verifier cause, causal status of the agent's behaviour, and the abstract
mechanism exposed — clustered by **exact triple equality**. Classification is rule-based
over a controlled vocabulary: a proposer inventing its own labels produces singleton
clusters, which defeats the purpose. Unmatched inputs yield `unknown` rather than a guess.

Two consequences matter more than the clustering itself:

- Environment failures (connection refused, rate limit, container died) classify as
  `environment_caused` and are therefore not mined as harness weaknesses.
- Repeat-aware: a `flaky` case gets its own signature, because the intervention it needs
  is stabilisation, not whatever its first failing repeat happened to print.

**Change (K).** `candidates` (default 1) proposes K variants per iteration, round-robining
them across clusters so they attack different root causes instead of restating one fix K
times. Each gets its own workspace (`.../proposer_workspace/kNN/`), decision record, and
ledger row. At most one is promoted: the winner is chosen by largest **holdout** gain with
train gain only as a tiebreak, because holdout is the split the proposer could not read.

## P2-6 — falsifiable predictions and flip attribution

**Problem.** An edit that comes with no prediction cannot be wrong — only kept or
discarded on a number nobody has to explain.

**Change.** New `better_harness/ledger.py`. The outer agent's prompt and the `proposal.md`
template now require a fenced JSON block committing to `root_cause`, `evidence`,
`flip_to_pass`, and `at_risk`. After evaluation the loop computes the actual stable
pass/fail flips and grades the prediction: precision, recall, misses, unexpected passes,
warned regressions, and — the one that matters most — **unpredicted regressions**, cases
that silently broke and were never flagged at risk.

Results accumulate into `ledger.json` and `ledger.md`. A missing or malformed prediction
block is recorded as a fact, never raised as an error.

Why this is worth having from iteration one: pass rate tells you whether the loop is
improving, prediction accuracy tells you whether it *understands why*. A proposer whose
predictions are no better than chance is running search, not engineering, and its gains
will not transfer. That signal is readable long before the pass-rate curve says anything.

## Not implemented

- No process isolation. The guard is static; a tool surface can still do what it likes at
  runtime.
- Signature rules are text heuristics over failure messages. They need extending per
  runner and per domain; the `unknown` rate is the metric to watch.
- No statistical test on the gate. `Δ >= 0` over attempt counts beats a single rollout,
  but it is not a paired significance test.
- No scorecard/locked-test discipline beyond upstream's: `scorecard` still runs on
  baseline and final only, which is the right shape, but nothing enforces a pre-registered
  access budget.

## Verify

```bash
uv sync --extra dev
uv run pytest -q          # 74 passed
uv run ruff check better_harness tests
```
