# Verification ladder

## Where this repo actually stands

**Implemented and software-verified:** the dual loop and rigor layer: isolated
product and harness workspaces, rollout → diagnose → propose → select, repeated
evaluation, conservative promotion, static guards, cost veto, deterministic
failure clustering, K candidates, candidate archive, and a falsifiable-prediction
ledger.

**Established in a deterministic fixture:** an outer harness edit causes a coding
agent to repair a disposable product and pass frozen CI while the product seed
stays unchanged. **Not established on FAB v2:** the first bounded live run produced
one plausible candidate, but train and validation deltas were both zero and the
gate rejected it. See the [case-study evidence](fabv2-case-study.md).

Those are different claims and it is worth keeping them apart. What has been verified is
**software correctness**. What has not been verified is **method efficacy**. A loop that
runs cleanly and promotes nothing useful looks exactly like a loop that works, right up
until you compare it against a baseline.

| Level | Question it answers | Status |
| --- | --- | --- |
| L0 | Does the code do what it says? | ✅ 149 tests, lint clean |
| **L0.5** | **Do the recorded numbers match what was measured?** | ✅ after Phase 0 — **it did not before** ([artifact fidelity](#l05--artifact-fidelity)) |
| L1 | Does the loop run with a **real** outer agent? | ✅ M1 2026-08-11, all 6 criteria ([results](results.md)) |
| L2 | What is the real baseline, and how noisy is it? | ✅ measured — MVP-1 saturated (0.917, 0 flaky) and the stop rule fired |
| L3 | Does the proposer understand what it is doing? | ⚠️ one graded prediction, **below base rate** (0.200 vs 0.286); n=1, underpowered ([results](results.md)) |
| L4 | Does evolution beat spending the same budget on retries? | ❌ not established; bounded FAB run had zero gain and did not include a retry arm |
| L5 | Does the gain survive a locked test and transfer? | ❌ post-MVP |

---

## L0 — software correctness ✅

```bash
uv sync --extra dev
uv run pytest -q                          # 149 passed
uv run ruff check better_harness tests    # All checks passed!
```

What the tests actually pin down, beyond "it runs":

| Claim | Test |
| --- | --- |
| Repeats count attempts, so `correctness` is pass@1 | `test_aggregate_counts_attempts_not_cases` |
| A flaky case never reads as a win | `test_aggregate_marks_flaky_and_keeps_stable_pass_semantics` |
| The proposer is shown a genuinely failing repeat | `test_aggregate_points_evidence_at_a_failing_repeat` |
| `repeats=1` reproduces upstream exactly | `test_aggregate_single_run_is_passthrough` |
| Conservative gate rejects what the combined gate promotes | `test_conservative_gate_rejects_robbing_holdout_to_pay_train` |
| A leaked case id never reaches the runner | `test_guard_rejects_a_leaky_candidate_without_spending_an_eval` |
| Compute knobs and verifier access are blocked | `test_guard_blocks_buying_or_grading_the_score` |
| Buying the score with 3x tokens is vetoed | `test_cost_veto_blocks_buying_the_score` |
| Unmeasured spend never reads as within budget | `test_unmeasured_spend_is_never_reported_as_within_budget` |
| Environment failures are not mined as harness weaknesses | `test_classify_environment_failure_is_not_blamed_on_the_agent` |
| Predictions are parsed, stored, and graded | `test_prediction_survives_into_the_ledger_and_is_graded` |
| K>1 yields K records, at most one promotion | `test_k_candidates_each_get_their_own_record` |
| A resumed run never reuses a result measured on a different harness | `test_resume_refuses_a_result_measured_on_a_different_harness` |
| Apparatus failures leave the numerator *and* the denominator | `test_apparatus_failures_leave_the_denominator` |
| A mostly-unmeasured evaluation cannot promote | `test_a_mostly_unmeasured_evaluation_cannot_promote` |
| Signatures read the error, not pytest's echo of the test source | `test_signature_reads_the_error_not_the_test_source` |
| One stage spanning two provider fingerprints fails | `test_one_stage_two_fingerprints_fails_the_stage` |
| A source file shared with a private split is never copied to the proposer | `test_a_source_file_shared_with_a_private_split_is_never_copied` |
| A surface that does not parse is rejected before any eval is spent | `test_a_surface_that_does_not_parse_is_rejected_before_any_eval` |
| The sealed split is evaluated once, not twice into one directory | `test_an_unpromoted_run_does_not_evaluate_the_sealed_split_twice` |
| A JUnit file with no `file` attribute still resolves to its case | `test_junit_without_a_file_attribute_still_resolves_to_its_case` |

### The bigger hole in L0, found the hard way

Every test above passed continuously while the repo's most protocol-loaded
number was wrong by ~90 percentage points. That is not a gap in the test suite;
it is a limit of what a test suite can do. **Unit tests verify that the code does
what the code says. They cannot verify that what the code says is what you meant
to measure.** `parse_pytest_outcomes` correctly recorded `missing → score 0` for
every case whose nodeid it failed to reconstruct — exactly as written, and
exactly wrong.

Nothing in L0–L5 as originally written would ever have caught it, because every
rung consumes `result.json` and asks questions *about* the numbers rather than
*of* them. Hence a new rung, below all of them.

---

## L0.5 — artifact fidelity

**Question:** does every recorded outcome match the raw evidence the runner
wrote?

```bash
uv run python scripts/verify_artifacts.py runs/*
```

The auditor re-derives every pass/fail straight from `junit.xml` and compares it
with `result.json`. It deliberately shares no code and no assumptions with the
parser under audit: each case directory holds the XML for exactly one case, so
the outcome is unambiguous without reconstructing any identifier — which is
precisely the step that was broken.

**What it found on first contact** (before the Phase 0 fixes):

| Run | recorded `final_scorecard` | true, from XML |
| --- | --- | --- |
| m2-baseline | 0/20 | **18/20** |
| b5-baseline | 0/20 | **17/20** |
| m2-baseline-rev0 | 0/20 | **18/20** |
| b5-baseline-rev0 | 0/20 | **18/20** |
| mvp2-baseline | 0/20 | **1/20** |

Train and holdout were clean in all five runs — every discrepancy sat in the
sealed split, so no experiment decision ever rested on a corrupted number. Had
MVP-1 reached its one permitted unseal, it would have published ~0/20.

**Rule:** no number from a run is admissible until this passes for that run.
Cost: seconds, zero rollouts.

### The original hole in L0

`invoke_deepagents_proposer` — and everything under it (`_invoke_via_uv_project_once`,
`_deepagents_import_context`, `_resolve_deepagents_root`, `_is_transient_model_error`) —
is **monkeypatched in every test in this repo**, upstream's included. The path that
actually talks to a model has zero coverage.

Everything above therefore verifies the loop *around* the outer agent. Whether the outer
agent can be invoked at all is L1, and it is the first thing to check, because a broken
integration there fails in a way that looks like "the model had no good ideas".

---

## L1 — loop liveness with a real outer agent

The cheapest possible real run: keep the toy fixture, swap the fake proposer for a live
model.

```bash
export DEEPAGENTS_ROOT=/path/to/deepagents      # or pip install deepagents
export ANTHROPIC_API_KEY=...
uv run better-harness validate examples/deepagents_example.toml
uv run better-harness run examples/deepagents_example.toml \
  --output-dir runs/l1-smoke --max-iterations 1 --repeats 1
```

**Pass criteria** — none of these are about pass rate:

1. `runs/l1-smoke/history/visible/iterations/001/proposer_workspace/` contains surface
   files the model actually rewrote (diff them against the baseline).
2. `proposal.md` contains a fenced JSON block, and `ledger.json` shows
   `prediction_made: true`. If it is `false`, the prompt is not landing — fix that before
   anything else, because L3 measures nothing without it.
3. `decision.json` carries a `gate` block with real deltas.
4. No guard violations of kind `undeclared_surface` (that would mean surface wiring is
   wrong, not that the model misbehaved).

**Cost:** one model call. Do this before spending anything on a benchmark.

---

## L2 — real baseline and its variance

Switch the runner to Harbor and a real task set. **Do not evolve yet.**

```bash
uv tool install harbor
# runner.harbor in the config; dataset terminal-bench@2.1
uv run better-harness run <config> --max-iterations 0 --repeats 5
```

Use **Terminal-Bench 2.1, not 2.0**: 2.1 is the verified revision that repairs 28 of the
89 tasks (dependency drift, resource budget mismatches, instructions misaligned with their
tests). Evolving against the unrepaired set risks learning to route around broken tasks,
which is indistinguishable from learning to solve them until you change benchmarks.

**What to record:**

- Baseline pass@1 with a bootstrap CI over `n_cases x repeats` attempts.
- The per-case flaky rate from `repeats.json`. This is the number that decides whether any
  later delta is readable at all.
- The **B5 baseline**: a mature harness (deepagents-cli, Claude Code) with zero evolution.
  This is the honest starting point, and it is the one number every published result in
  this area omits.

**Stop condition:** if the flaky rate is high enough that the baseline CI is wider than
the effect you hope to detect, no amount of evolution will produce a readable result.
Raise `repeats`, clean the task set, or pick a different benchmark. Do not proceed.

---

## L3 — does the proposer understand what it is doing?

Run 3–5 evolution iterations. **Read the ledger, not the pass rate.**

```bash
uv run better-harness run <config> --output-dir runs/l3 --max-iterations 5
cat runs/l3/ledger.md
```

Pass rate over 5 iterations on a small task set is mostly noise. Prediction accuracy is
readable immediately, and it answers a different and more useful question: is this
proposer reasoning about mechanisms, or generating plausible text and getting graded?

**Pass criteria:**

| Signal | Healthy | Bad |
| --- | --- | --- |
| `precision` (predicted flips that landed) | clearly above the base rate of "any given failing case flips" | at or below it — the proposer is guessing |
| `unpredicted_regressions` | near zero | recurring — edits have reach the proposer does not model |
| `unknown` rate in signature clusters | low | high — the rule vocabulary does not fit this domain, so clustering is doing nothing |
| Guard rejections | occasional, and of kind `forbidden_pattern` | frequent `case_id_leak` — the proposer's instinct is to memorise |

Compute the base rate before reading precision: with `f` failing cases and a prediction
naming `k` of them, chance-level precision is roughly (flips that occurred) / `f`. A
proposer that predicts the three most obviously broken cases and hits two is not
demonstrating insight.

---

## L4 — the decisive test

**This is the one that decides whether the project is worth continuing.** Harness
evolution is itself a search procedure that repeatedly evaluates and revises candidates.
Compared against nothing, it always looks good.

Run **B1**: the seed harness, unchanged, with best-of-N retries, where N is chosen so
total spend matches the evolution run's total spend (report both token-matched and
rollout-matched).

```
evolution:  runs/l4-evolve   (K candidates x M iterations x repeats)
B1:         same total rollouts spent on retrying the seed
```

**Pass criteria:** evolution beats B1 on the **validation** split by a margin larger than
the baseline CI from L2, reproducibly across at least two seeds.

If it does not, stop. Published work using Terminal-Bench 2.1 already reports that
automatic harness evolution does not consistently beat test-time scaling and generalizes
poorly to held-out tasks. A negative result here is the expected outcome, not a surprise,
and it is worth far more than a number you cannot defend.

---

## L5 — does the gain survive?

Only if L4 passed.

1. **Locked test.** Unseal the `scorecard` split once. The gain there should be at least
   half the validation gain. Anything less means the loop was climbing validation.
   *Note:* nothing in this code enforces a pre-registered access budget on `scorecard` —
   it runs on baseline and final only, which is the right shape, but the discipline is
   yours to keep. Write down how many times you will look before you look.
2. **Gain concentration.** If more than ~70% of the improvement comes from 2–3 tasks, it
   is luck or memorisation, not method. `ledger.json` has the per-iteration flip lists to
   compute this.
3. **Transfer.** Freeze the harness, change the base model, re-run without evolving. Then
   change benchmarks (SWE-bench-Verified subset). No transfer means the harness learned
   the benchmark, not engineering.
4. **Cost.** Check the `budget` block in `decision.json` across the run. A correctness
   gain bought with a large spend increase is a different product, not a better one.

---

## What would falsify this whole line of work

Worth writing down before running anything, so the answer is not negotiated after the
fact:

- **L3 fails:** prediction accuracy at chance → this is search wearing engineering's
  clothes. The evidence-driven premise is wrong for this setup.
- **L4 fails:** loses to equal-budget best-of-N → the method adds nothing over retries
  here, whatever the pass-rate curve looks like in isolation.
- **L5.1 fails:** locked-test gain far below validation gain → overfitting, and the
  earlier numbers were measuring the search, not the harness.
- **L5.3 fails:** no transfer → benchmark-specific tuning. Real, but not what was claimed.

Any one of these is a result worth reporting. None of them is a reason to keep tuning
until the number moves.
