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
| `[experiment]` config | new `repeats` (default 3) and `gate` (default `conservative`) |
| CLI | `run --repeats N`, `run --gate {conservative,combined}` |
| `validate` | prints repeats and gate |
| `report.md` | prints repeats and gate, and warns when repeats < 3 or gate is `combined` |
| `decision.json` | adds `holdout_passed`, `holdout_total`, `gate` block |
| Split dirs | `<split>/<variant>/repNN/` plus aggregated `result.json` + `repeats.json` when repeats > 1 |

## Upstream tests

`test_run_end_to_end_pytest_demo` and `test_run_end_to_end_harbor_backend` asserted
absolute pass counts, which now scale with `repeats`. They assert
`n * report.repeats` and `correctness == 1.0` instead, so they exercise the repeat path
rather than pinning it to 1.

## Still missing (P1/P2, not implemented here)

- **P1-3 edit guard** — no path allowlist, no diff check, no scan for task ids or test
  literals leaking into harness text. Upstream README is explicit that the
  visible/private split "is not a hard sandbox boundary yet".
- **P1-4 cost gate** — only `duration_s` is captured. No tokens, no cost, no p95 latency,
  so a candidate can buy pass rate with a 10× spend and the gate will not notice.
- **P2-5** — one candidate per iteration (K=1); no failure-signature clustering.
- **P2-6** — no falsifiable prediction per edit, no flip attribution ledger.

## Verify

```bash
uv sync --extra dev
uv run pytest -q          # 29 passed
uv run ruff check better_harness tests
```
