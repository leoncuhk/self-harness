# MVP results — terminated at M2 by the pre-registered stop rule

**Date:** 2026-08-11 · **Verdict:** the MVP stopped at M2, exactly as its frozen
protocol requires. **Method efficacy was not tested** — the testbed saturated: the
inner model solves the task suite at baseline, twice, leaving no headroom for any
harness improvement to be detected. That is a result about the testbed, not about
self-harness, and this document does not claim otherwise in either direction.

## What happened, in order

| Stage | Outcome |
| --- | --- |
| M1 (real-loop smoke, toy fixture) | ✅ all 6 criteria; live deepseek proposer rewrote 4 surfaces, prediction precision 1.0, 201,787 proposer tokens |
| Suite build | 16 authored agentic tasks, real deepagents inner agent, deterministic verifiers, committed before first rollout |
| Wiring smoke (2 real rollouts) | ✅ 1 pass / 1 real failure, ~17 s and ~17 k tokens per rollout |
| M2 baseline rev0 (16×5 + B5 16×5) | train **0.875**, holdout **1.000**, 0 flaky — outside the frozen window [0.20, 0.85] |
| Difficulty revision 1 (the only one permitted) | all 16 tasks hardened by compounding exactness requirements; committed before rerun |
| M2 baseline rev1 (16×5 + B5 16×5) | train **0.875**, holdout **1.000**, 0 flaky — same numbers, same single failing task |
| Frozen rule | combined 11/12 = 0.917 > 0.85, revision budget spent → **stop** |
| M3 / M4 / scorecard unseal | **cancelled per protocol.** The scorecard was never read and remains sealed |

## The two load-bearing facts

**1. The suite is fully deterministic for this model.** Across 20 rollouts per task
(5 repeats × 2 revisions × 2 configs), not one case was flaky: `temperature=0` plus
explicit instructions yields the same trajectory every time. Good for measurement —
fatal for headroom when the model is strong enough, because pass@1 sits at 0 or 1
per task with nothing in between.

**2. deepseek-v4-flash is far stronger on explicit-instruction agentic tasks than
the design assumed.** The revision added quoted-CSV parsing with per-file discounts,
ordinal dates with a leap-year trap, two-digit-year formats, multi-key sort orders,
conditional checksums, a distractor whose shortcut matches the wrong column, and
NBSP normalisation. The model solved every one of them, first try, at baseline —
15/16 tasks in both revisions.

The single deterministic failure, both times, was `fmt-fixed-width` — column
budgeting. Rev1 detail:

```
expected: 'bolt           42     0.35'   (name<12 | qty>5 | price>9)
got:      'bolt           42    0.35'    (price right-justified one short)
```

A stable, mechanistic, clusterable failure — precisely what box ② exists to catch,
and it would have been M3's single target cluster. The protocol stopped M3 anyway,
correctly: one deterministic failure on 8 train cases cannot support an efficacy
claim, and holdout at 1.000 makes the M4 margin undetectable *by construction*.

## Why the stop rule is the right outcome, not a failure of nerve

The alternative was a third difficulty pass — tuned, task by task, against a model
whose failures I can now see. That is the exact experimenter-degrees-of-freedom
loop the pre-registration exists to forbid: by iterating "make it harder until the
model fails", the task set becomes a fingerprint of the model's blind spots, and
any subsequent "improvement" measures my tuning, not the harness loop. The window
rule (one revision, then final) was written before any data; it fired; the
experiment stopped. **This is the pre-registration working, and it is worth more
than a positive-looking number produced by ignoring it.**

## What is established vs. not

Established (with evidence in-repo):

- The full four-box loop runs end-to-end with a live model on both sides
  (proposer: M1; inner agent: 320+ real rollouts) — the previously untested
  `invoke_deepagents_proposer` path included.
- Surfaces are genuinely loaded at runtime; token accounting works on every rollout
  (M2 rev1: 1,792,962 inner-agent tokens, per-case in `summary.json`).
- Repeats, gate, guards, clusters, and the prediction ledger all produced real
  artifacts on real runs.
- B5 (deepagents stock prompt, zero evolution) equals the minimal seed baseline on
  this suite — on saturated tasks, prompt maturity contributes nothing measurable.

Not established, in either direction:

- Whether the evolution loop improves a harness (M3 never ran under protocol).
- Whether evolution beats equal-budget retries (M4 never ran).
- Anything about generalisation, transfer, or locked-test survival.

## Diagnosis: where the headroom design failed

The design leaned on the published claim that mid-tier models benefit most from
harnesses, and slotted deepseek-v4-flash in as "mid-tier". Two errors compounded:

1. **Tier misjudged.** On short-horizon, fully-specified, file-manipulation tasks
   at temperature 0, this "flash" model behaves like a frontier model. Tier labels
   track price, not capability-on-your-distribution.
2. **Task family mismatched to the lever.** Explicit instructions + deterministic
   verifiers leave exactly one failure mode standing (execution discipline), and a
   strong model has already internalised most of that discipline. The harness
   lever needs tasks where *strategy* — planning, verification, recovery — is the
   bottleneck: long-horizon, under-specified, environment-heavy tasks. That is
   TB2.1-class territory, which is what the original (pre-amendment) M2 named.

## Paths forward — each requires a fresh pre-registration

1. **TB2.1 via harbor** (the original confirmatory step): open-ended terminal
   tasks, published baselines far from ceiling. Costs the custom-agent integration
   that Amendment 1 deferred.
2. **Same suite, genuinely weaker inner model** (a small open model): keeps the
   cheap infrastructure, tests the mid-tier-benefit hypothesis honestly. Proposer
   can stay deepseek — that separation is itself informative (updater ≠ beneficiary).
3. **Open-ended task family** (goal-specified, method-unspecified, multi-constraint)
   where even strong models land mid-range at pass@1.

Option 2 is the cheapest next experiment and the only one runnable in hours; option
1 is the one whose result would be externally comparable.

## Spend

~322 real inner-agent rollouts + 1 proposer invocation ≈ **6M tokens** on
deepseek-v4-flash across M1, smoke, and four baseline campaigns (M2/B5 × rev0/rev1).
No scorecard output was ever read; `runs/*-rev0` and rev1 run dirs are preserved.

## Protocol-execution gaps, disclosed

- **Per-rollout `system_fingerprint` logging was promised in the MVP-1 pre-registration ([mvp.md](../development/mvp.md)) but not
  implemented during the four baseline campaigns** — provider drift was unmonitored
  while they ran. Closed after the fact (`agent_harness.run_task` and the eval
  summary now record fingerprints), so it holds for future runs, not
  retroactively for these.
- The cost-veto path on this suite was never exercised under evolution (M3
  cancelled); it remains verified only at the unit-test level.

---

# MVP-2 — in progress

Pre-registration: [mvp.md](../development/mvp.md#mvp-2-pre-registration). Execution log, appended
as stages complete.

## Calibration (2026-08-11)

All probes reported per the frozen rule:

| Candidate | Tool smoke | Baseline (repeats=3) | Verdict |
| --- | --- | --- | --- |
| qwen3-4b | ❌ provider 403 | — | excluded |
| qwen3-8b | ❌ provider requires `enable_thinking=false` param not in standard config | — | excluded |
| **gpt-4.1-nano** | ✅ | train 0.125, holdout 0.500, **combined 0.25 ∈ [0.20, 0.85]** | **selected** |
| gpt-4o-mini | ✅ | not needed | — |
| gpt-4.1-mini | ✅ | not needed | — |

Calibration observations (`runs/calib-nano`): 6/8 train tasks fail outright
(invoice discounts, fixed-width, checksum, distractor, empty-edge, invoice
quoting); 3 train tasks are genuinely **flaky at temperature 0** (pass fraction
0.33) — the first non-degenerate data for the repeats machinery. Holdout has real
headroom (0.50) with a wide CI (±0.50 at n=4), as the power disclosure anticipated.

Inner agent: `openai:gpt-4.1-nano`. Proposer: `openai:deepseek-v4-flash`
(updater≠beneficiary configuration, disclosed in the pre-registration).

## MVP-2 reference baseline (repeats=5, `runs/mvp2-baseline`)

Train 7/40 = **0.175**, holdout 10/20 = **0.500**, combined 0.283 — in window,
consistent with calibration. Flakiness is real for this model (calibration showed
0.33 pass fractions), so the repeats machinery is load-bearing for the first time.

**Disclosure — accidental scorecard exposure.** The stage log prints the run
report, which includes the baseline scorecard aggregate (≈1/20). This was seen
while checking progress, violating the letter of the read-nothing rule. Scope of
exposure: aggregate count only, baseline harness only, no task-level detail, and
no experiment decision was or will be taken from it. The M4 verdict is
holdout-based; the one permitted unseal still applies to the evolved harness.
Lesson filed: filter run logs (`grep DONE`) instead of tailing them when a run
touches scorecard.

## M3 (evolution) — not completed as of 2026-08-11 22:23

Four launches, no stage marker written by any of them; `runs/mvp2-evolve` holds
only the baseline train rollouts. Failure mode each time: `APIConnectionError` /
`RemoteProtocolError: Server disconnected` inside a langgraph `model`/`tools`
node, mid-stage.

Two mitigations shipped and neither closed it: proposer-path retries
(5 attempts, 5–20 s backoff, `e589350`) and `caffeinate -is` against idle sleep
(`0d16736`). What both miss:

- **The inner agent has no retry and no per-request timeout** — `run_task` calls
  `agent.invoke` bare, so a proxy blip during any of the ~180 M3 rollouts is
  unhandled. Retry coverage is proposer-only.
- **A run has no checkpoint.** A crash in iteration 3 discards the rollouts of
  iterations 1–2 entirely; expected cost to finish therefore grows with run
  length instead of staying flat, which is why every attempt has died before the
  end.

Registered as gap 5 in the [roadmap](../development/roadmap.md); items A1/A2 are the fix, and
they are infrastructure only — no information reaching the proposer changes, so
they do not touch the frozen MVP-2 protocol.

**Run stopped 2026-08-11 22:5x, deliberately, four iterations in.** Not because
of a crash — because an audit of the instrument found the run inadmissible while
it was still going. See the correction below.

---

# Correction — instrument defects found 2026-08-11, and what they change

An audit re-derived every recorded outcome from the raw `junit.xml`
([L0.5](verification.md#l05--artifact-fidelity)). Five findings, all reproduced
from artifacts in `runs/` before anything was changed.

## 1. Every sealed-split number in the repo was wrong

`final_scorecard` reads **0/20 in all five baseline runs**. The true values,
recovered from the XML:

| Run | recorded | true | per-case |
| --- | --- | --- | --- |
| m2-baseline | 0/20 | **18/20** | 5/5, 5/5, 4/5, 4/5 |
| b5-baseline | 0/20 | **17/20** | 5/5, 5/5, 2/5, 5/5 |
| m2-baseline-rev0 | 0/20 | **18/20** | 5/5, 5/5, 3/5, 5/5 |
| b5-baseline-rev0 | 0/20 | **18/20** | 5/5, 5/5, 3/5, 5/5 |
| mvp2-baseline | 0/20 | **1/20** | 1/5, 0/5, 0/5, 0/5 |

**One causal chain, not two defects** — an earlier version of this document and
of commit `2369fc7` described them as independent, which was wrong.

pytest treats every non-option argv token as a possible path and keeps the ones
that **already exist** when it computes rootdir
(`_pytest/config/findpaths.py`: `[... for path in possible_paths if safe_exists(path)]`).
The *values* of `--junitxml` and `--evals-report-file` are such tokens. So:

| | artifact files | rootdir | emitted classname | old parser |
| --- | --- | --- | --- | --- |
| 1st run into a case dir | absent → ignored | evals project | `tests.test_agentic` | ✅ resolves |
| 2nd run into the same dir | present → treated as paths | **repo root** | `benchmarks.agentic.evals.tests.test_agentic` | ❌ no match → `missing → 0` |

The double evaluation of the sealed split did not merely *coincide* with the
parse defect — it was the **trigger** for it. Confirmed by scanning classname
shapes across every `junit.xml` in `runs/`:

```
 20  b5-baseline      scorecard  LONG      40  b5-baseline    train   short
 20  m2-baseline      scorecard  LONG      20  m2-baseline    holdout short
 20  mvp2-baseline    scorecard  LONG      …
 10  mvp2-evolve      train      LONG   ← not scorecard
```

That last row is the important one: **resume is the same trigger.** Any stage
restarted with `--resume` re-runs into existing case directories and lifts
rootdir exactly the same way. The 10 long-shape train files in `mvp2-evolve`
match, one for one, the 10 discrepancies the auditor found in that run.

Three fixes, at three levels: the artifact paths are now cleared before pytest
is invoked (so rootdir no longer depends on how many times a case has run); case
ids resolve by matching candidate nodeids against the configured ids by path
suffix rather than by guessing a shape; and a junit that records testcases none
of which can be mapped now raises `UnresolvedCaseError` instead of scoring zero.
A junit with *no* testcases — a killed rollout — is apparatus, not an error, so
one dead rollout cannot abort a 180-rollout stage.

The sealed split is also no longer evaluated twice when nothing was promoted.

**What this does and does not change.** No experiment decision ever rested on a
scorecard number — MVP-1 stopped on train/holdout, and Amendment 2's arithmetic
rests on holdout. But had MVP-1 reached its one permitted unseal, it would have
published ~0/20 as its locked-test headline against a true 18/20.

## 2. Train and holdout are clean

Zero discrepancies outside the scorecard split in all five runs. **The MVP-1 and
MVP-2 baselines stand as measured**, and Amendment 2's conclusion is unaffected.

## 3. Nearly half the measured failures were not task failures

`runs/mvp2-baseline`, per-repeat, 80 rollouts / 17 passed / 63 failed:

| | count | what it is |
| --- | --- | --- |
| assertion | 23 | real task failure |
| `GraphRecursionError` | 20 | step budget exhausted — **`RECURSION_LIMIT = 60`, a frozen constant no editable surface can reach** |
| junit unreadable | 20 | never measured (all 20 scorecard rollouts) |

So of the 43 train+holdout failures, **20 (47%) point at a lever the proposer is
forbidden to pull**. That is a testbed design fault, not a model result: the
literature treats runtime control policy (error caps, tool-message caps) as an
*editable* component, and here it is welded shut.

## 4. The failure classifier was confidently wrong, in a fixed direction

Measured on the real messages, before the fix:

| input | φ(r) |
| --- | --- |
| `GraphRecursionError` | `unknown / undetermined / unknown` |
| junit unreadable | `unknown / undetermined / unknown` |
| broken middleware | `unknown / undetermined / unknown` |
| **a real assertion failure** | **`timeout / agent_caused / unbounded_retry_loop`** |

The three instrument failures landed in `unknown`; the one genuine task failure
got a confident, wrong mechanism — because pytest echoes the test source into
the failure message and this suite's `@pytest.mark.timeout(420)` decorator
matched the `timeout` rule. Box ② was telling the proposer the agent looped on
retries when it had mis-padded a column.

## 5. The frozen fingerprint rule had already fired, unenforced

`runs/mvp2-evolve` spans `fp_e010545658` (74 rollouts) and `fp_65c6c2730f` (66)
against a single-fingerprint baseline. MVP-2's frozen rule voids a stage whose
provider model changed mid-run. No code enforced it; there is now.

## Also observed in the four completed M3 iterations

- **iteration 1** — the only substantive proposal — was rejected by the bloat
  guard at 7770B from a 783B seed (9.92×).
- **iteration 2** was admitted at 3725B (4.76×, *58% over the same ratio*)
  because it fell under the 4096B absolute floor, then failed to load in all 24
  train attempts: `TypeError: break_retry_loops() missing 1 required positional
  argument: 'config'`. The gate recorded it as a harness regression
  (Δ_in=-1, Δ_ho=-3). A 60-second import check would have caught it; there is
  now a static one, and `harness_did_not_load` is a named signature.

## Status

MVP-2's M3 is void and was re-run on the corrected instrument. The
pre-registration is unchanged in every respect that governs a decision; the
instrument changes are recorded in [mvp.md](../development/mvp.md) Amendment 3.

---

# MVP-2 M3 on the corrected instrument — terminated incomplete at iteration 3

**Run:** `runs/mvp2-evolve-v2`, code at commit `d400ec1`, working tree clean.
**Outcome:** 2 of 5 iterations completed. The run could not continue, for a
reason that is itself a finding rather than bad luck (see *Why it stopped*).

## The instrument held

**[L0.5](verification.md#l05--artifact-fidelity) passes for the first time in
this repo's history:** 168 cases audited, recorded passed 35 = derived passed
35, **zero discrepancies**. Apparatus failures: **0** on every split. One
provider fingerprint throughout (`fp_e010545658`), no drift.

The corrected baseline reproduces the old one within noise — train
0.125 (3/24) against the previous 0.175, holdout 0.500 (6/12) exactly — so the
fixes changed what is *recorded*, not what is *measured*.

## What the two iterations show

| Iteration | Outcome |
| --- | --- |
| 1 | rejected by the edit guard: `surface_bloat`, 4717B from a 783B seed (6.02× > 3.00×). No evaluation spent |
| 2 | evaluated, then rejected by the conservative gate: **Δ_in=+5, Δ_ho=−5** |

Iteration 2 is the textbook case P0-2 exists for. Per split:

| | baseline | candidate |
| --- | --- | --- |
| train (visible) | 3/24 = 0.125 | **8/24 = 0.333** |
| holdout (invisible) | 6/12 = 0.500 | **1/12 = 0.083** |

Per case — train flips `fmt-fixed-width` and `rb-empty-edge` to passing and
breaks `ms-even-pipeline`; holdout breaks `fmt-json-report` and
`rb-messy-names`, which were both stably passing at baseline. The edit bought
visible cases with invisible ones. Upstream's `combined` gate would have scored
this Δ_in+Δ_ho = 0 and also rejected it, but only by a hair.

## L3 — the prediction ledger, read before the pass rate

The proposer's own frozen prediction for iteration 2, graded against what
actually happened:

| | |
| --- | --- |
| predicted to flip | 5 cases |
| actually flipped | 1 of those 5 (`fmt-fixed-width`) |
| **precision** | **0.200** |
| **base rate** (flips ÷ failing cases on the visible split) | **2/7 = 0.286** |
| unexpected pass | `rb-empty-edge` — flipped without being predicted |
| regressions it warned about | `ms-even-pipeline` — **1 of 1** it could see |
| unpredicted regressions | `fmt-json-report`, `rb-messy-names` — both holdout, structurally invisible to it |

**Precision 0.200 is below the 0.286 base rate.** Under the frozen reading
rule: *at or below base rate → the proposer is guessing; this caps the claim at
"search", not "engineering".* Recorded as such.

Two qualifications, in both directions. Against the proposer: this is the
number the pre-registration said to read first, and it is negative. In its
favour: **n = 1 evaluated candidate.** One iteration cannot separate a guessing
proposer from an unlucky one, and its two unpredicted regressions were in a
split it is not allowed to see, so they are a property of the design rather than
of its reasoning. The honest summary is that MVP-2 produced **one** L3 data
point, and it did not clear the bar.

## The diagnosis was right; the edit that fit was not

Both proposals identified the same root cause, and it is mechanically correct:

> the harness provides no code-execution capability and no pre-submit
> verification requirement, so the agent estimates derived values (counts, sums,
> date parses, column widths) and writes the first answer it believes.

That is a true statement about this suite — the tasks require exact arithmetic
and formatting, and the inner agent has no code execution. Box ② was diagnosing,
not pattern-matching. But:

- the edit that acts on that diagnosis (add a code-execution tool) **exceeded the
  bloat guard** and was rejected at iteration 1;
- the edit that fits under the guard **improved train and destroyed holdout**.

So on this configuration, edits that fit the 3× budget do not generalise and
edits that generalise do not fit. That is a property of the frozen config, not
of the model. The thresholds were left untouched; registered for MVP-3.

## Why it stopped — and why that is a finding

Iteration 3's proposer call never completed, across two independent attempts
(the original run and a `--resume`). Each attempt failed with
`APIConnectionError` after 272–545 s, and the wall-clock retry budget (600 s)
permits roughly one retry when a single attempt costs that much.

This is **not** random provider flakiness, and the evidence separates the two:

| | context per request | transport failures |
| --- | --- | --- |
| inner-agent rollouts (72 of them) | ~17k tokens total per rollout | ≈ 0 |
| direct probe | ~20 tokens | 0 (HTTP 200 in 1.5–2.9 s) |
| **proposer calls** | **largest single request 78,065 input tokens** | **every attempt** |

The proposer's transcripts run 60–76 messages and 0.9–1.3M cumulative tokens per
iteration. Small requests return in seconds; large ones are dropped after
minutes.

The methodological half of this matters more than the infrastructure half.
Self-Harness (2606.09498) specifies a **bounded proposal context** — editable
surfaces, structured failure patterns, passing behaviour to preserve, prior edit
records. This implementation's proposer workspace additionally carries copied
prior-iteration artifacts, visible history, and train case sources, and the
context reaches 78k tokens. **A proposer swimming in 78k tokens of its own
history is the harness-bloat failure this project warns about, occurring in the
outer loop — while a guard downstairs rejects a 3× expansion of the inner one.**

Registered for MVP-3 under two headings, and deliberately **not** fixed
mid-experiment:

1. *Infrastructure* — iteration-internal checkpointing, so a proposer call that
   dies does not discard the whole iteration ([roadmap](../development/roadmap.md) gap 5, finer grained).
2. *Method* — bound the proposer's context. This is the fix that addresses the
   transport symptom and the fidelity-to-the-paper problem at once, and it may
   well be improving proposal quality rather than merely enabling the run.

## What MVP-2 can and cannot claim now

Established: the corrected instrument records what it measures (L0.5 passes,
0 apparatus, no fingerprint drift); the conservative gate caught a real
holdout-robbing edit that the combined gate would have nearly promoted; the
proposer produces a mechanically correct diagnosis; one graded prediction landed
below its base rate.

Not established: anything about efficacy, about L3 with usable statistical
power, or about L4. MVP-2 stops here as an **incomplete L3 experiment with a
single graded prediction**, and the next question belongs to a fresh
pre-registration.
