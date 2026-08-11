# MVP plan — pre-registered

Written **before** any real run. The decision criteria in this file are frozen: after
numbers exist, they may be reported against, not renegotiated.

## What the MVP is

The smallest complete run that produces **evidence about method efficacy** — not more
machinery. Concretely: a real proposer model, a real task set with a frozen verifier, a
measured baseline, an evolution run, and an equal-budget comparison, all under the
criteria below.

**Explicitly out of scope** (post-MVP): full TB2.1 (89 tasks), multi-seed replication,
model/benchmark transfer (L5.3), K>2 candidates, runtime sandboxing, signature-rule
tuning beyond what M3 forces.

The MVP answers one question: *on this task set, does one full evolution run beat
spending the same budget on retries of the seed harness?* It does not claim
generality, transfer, or reproducibility — those are L5 and multi-seed work.

## Stages

### M1 — real-loop smoke (= VERIFY L1)

Toy fixture, live proposer. One to three model calls.

```bash
export DEEPAGENTS_ROOT=... ANTHROPIC_API_KEY=...
uv run better-harness run examples/deepagents_example.toml \
  --output-dir runs/m1-smoke --max-iterations 1 --repeats 1
```

Pass criteria (none are pass-rate): surfaces actually rewritten (diff vs baseline);
`prediction_made: true` in ledger; `decision.json` has a real gate block; no
`undeclared_surface` guard violations.

**M1 additionally must verify token accounting**: confirm the runner's `summary.json`
contains a usable token/cost field and that `cost.py` reads it. If spend is
unmeasurable, M4 degrades from token-matched to rollout-matched comparison — decide and
record which one the MVP claims **before** M4 runs.

### M2 — task set and baseline variance (= VERIFY L2)

**Task set: Terminal-Bench 2.1 subset, 16 tasks** (8 train / 4 holdout / 4 scorecard,
stratified by task category), via the harbor runner.

Why not deepagents' own `libs/evals`: several of those evals are LLM-judged, which
breaks the frozen-evaluator premise (evaluator noise becomes indistinguishable from
harness effect). TB2.1 verifiers are deterministic tests. Use **2.1, not 2.0** (28/89
tasks repaired in 2.1).

**Selection is pre-registered to avoid picking winnable tasks:** stratified random
sample from the cleaned task list, RNG seed recorded in this repo before any per-task
results are viewed. No swapping tasks after seeing failures.

Run baseline only, no evolution:

```bash
uv run better-harness run <tb-config> --max-iterations 0 --repeats 5
```

Record: pass@1 with bootstrap CI over attempts; per-case flaky rate from
`repeats.json`; **B5** (a mature harness — deepagents-cli defaults — zero evolution)
as the honest starting point.

**Stop condition (frozen):** if the baseline CI half-width exceeds ~10pp on this task
set, deltas will not be readable; raise repeats or grow the task set before evolving.
Do not proceed on hope.

### M3 — evolution, read the ledger first (= VERIFY L3)

5 iterations, K=1 (K=2 only if M2 shows ≥3 distinct failure clusters), repeats=3,
conservative gate, guards and budget enabled.

Read order: `ledger.md` before `report.md`. Signals, with frozen interpretations:

- Prediction precision vs base rate (flips-that-occurred / failing-cases). At or below
  base rate → the proposer is guessing; record it, this alone does not stop the MVP but
  it caps the claim at "search", not "engineering".
- `unpredicted_regressions` recurring → edits have unmodeled reach.
- Signature `unknown` rate > 50% → clustering is doing nothing on this domain; note
  that box ② has degenerated to untargeted proposing. Record, continue.
- Guard rejections of kind `case_id_leak` → the proposer's instinct is memorisation.

Manual audit: every **promoted** diff is read by a human before M4. MVP scale makes
this cheap; it is the runtime-sandbox substitute.

### M4 — equal-budget comparison (= VERIFY L4, single-seed)

**B1:** the seed harness, unchanged, best-of-N retries, N chosen to match the evolution
run's total spend (token-matched if M1 confirmed accounting; else rollout-matched, and
the writeup says so).

**Decision rule (frozen):**

- Evolution beats B1 on the **holdout** split by more than the M2 baseline CI
  half-width → MVP positive; proceed to multi-seed L4 and L5.
- Otherwise → MVP negative; write it up as a negative result. Published TB2.1 work
  already reports harness evolution failing to beat test-time scaling, so this outcome
  is *expected*, not a malfunction to be tuned away.

**Not** grounds for continuing to tune: "it almost cleared the bar", "one task was
unfair", "the proposer had a bad day". One evolution run, one B1 run, one comparison.

### Scorecard access budget (frozen)

The `scorecard` split is unsealed **exactly once** in the entire MVP: after the M4
decision, to measure validation-vs-locked-test gap. Nothing in the code enforces
this; this paragraph is the enforcement. If scorecard is touched earlier for any
reason, the MVP's locked-test claim is void and the writeup must say so.

## Rough budget

| Stage | Rollouts | Proposer calls |
| --- | --- | --- |
| M1 | ~6 (toy) | 1–3 |
| M2 | 16 × 5 = 80 (+ B5 ≈ 80) | 0 |
| M3 | 5 iters × 12 cases × 3 repeats ≈ 180 | 5 |
| M4 | B1 ≈ 180 | 0 |
| Scorecard | 4 × 3 × 2 ≈ 24 | 0 |
| **Total** | **~550 rollouts** | **≤ 8** |

At TB-typical rollout cost this is tens of dollars, not hundreds — dominated by M2–M4
inner-agent rollouts, not by the proposer.

## Pre-spend fix list

Before M2 spends anything:

- [ ] M1 passed, including token-accounting verification.
- [ ] Paired bootstrap p-value **reported** alongside gate deltas (report-only; the
      gate's behaviour is unchanged — changing the gate now would invalidate the A/B
      against upstream's `combined` mode).
- [ ] Model IDs, temperature, and dates pinned in the TB config.
- [ ] TB2.1 subset drawn by recorded RNG seed, committed before any per-task run.
- [ ] This file committed, so the criteria predate the data.

## Validity audit — what the MVP can and cannot claim

Threats, in decreasing order of how much they could corrupt the conclusion:

1. **Evaluator not frozen.** Mitigated by choosing TB2.1 deterministic verifiers over
   LLM-judged evals. Residual: container/env flakiness — mitigated by repeats and by
   `environment_caused` signature classification keeping infra noise out of box ②.
2. **Budget matching is fake.** If token accounting fails, "equal budget" silently
   means "equal rollouts", which favors whichever side has cheaper rollouts. Handled:
   M1 verifies accounting; the writeup states which matching was used.
3. **No significance test in the gate.** Δ≥0 over attempts is not a paired test.
   Handled at MVP scale by (a) reporting bootstrap p-values, (b) the M4 decision using
   the CI half-width, not the gate. The gate decides *promotion during search*; the
   *conclusion* rests on M4's criterion.
4. **Tiny task set → gain concentration is inevitable.** 1–2 flips on 16 tasks is the
   entire effect. Handled by scoping the claim: "on this task set", never "in
   general". Gain concentration is reported as description, not judged as failure —
   the sample is too small for that criterion to be meaningful.
5. **Single seed.** The MVP claims existence, not reproducibility. Stated in the
   writeup; multi-seed is the first post-MVP step if positive.
6. **Task selection bias.** Handled by pre-registered stratified random sampling.
7. **Static guard is not a sandbox.** A tool surface could still misbehave at runtime.
   Handled at MVP scale by human audit of every promoted diff.
8. **Proposer and inner agent share a model family.** The result claims
   self-improvement *for this configuration*; cross-model updater→beneficiary transfer
   is L5.
9. **Signature vocabulary untested on TB.** High `unknown` rate expected on first
   contact; it is a measured limitation, not silently absorbed.
10. **Experimenter degrees of freedom.** The main defense is this document's ordering:
    criteria frozen before data, one decision point (M4), one scorecard unseal, and
    negative results are a deliverable, not a bug.

## What the MVP deliverable looks like

Either outcome produces the same artifact: a short writeup with the M2 baseline + CI,
the M3 ledger summary (prediction precision vs base rate, unknown rate, guard log),
the M4 comparison with the pre-registered rule applied, and the single scorecard
number. Positive → proceed to L4 multi-seed / L5. Negative → the writeup *is* the
result, and the next question is which box of the loop failed (③ proposals weak? ②
clusters uninformative? ④ gate starved?) — answerable from the same artifacts.
