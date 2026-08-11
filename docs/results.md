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

- **Per-rollout `system_fingerprint` logging was promised in the MVP-1 pre-registration ([mvp.md](mvp.md)) but not
  implemented during the four baseline campaigns** — provider drift was unmonitored
  while they ran. Closed after the fact (`agent_harness.run_task` and the eval
  summary now record fingerprints), so it holds for future runs, not
  retroactively for these.
- The cost-veto path on this suite was never exercised under evolution (M3
  cancelled); it remains verified only at the unit-test level.

---

# MVP-2 — in progress

Pre-registration: [mvp.md](mvp.md#mvp-2-pre-registration). Execution log, appended
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

Registered as gap 5 in the [roadmap](roadmap.md); items A1/A2 are the fix, and
they are infrastructure only — no information reaching the proposer changes, so
they do not touch the frozen MVP-2 protocol.
