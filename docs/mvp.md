# Pre-registration registry

Chronological, append-only. Each entry is frozen before its data is collected;
outcomes are recorded against entries, never by rewriting them.

- **MVP-1** (below) — terminated at M2 by its stop rule; see [results](results.md).
- **[MVP-2](#mvp-2-pre-registration)** (end of file) — L3 on the same suite with a
  calibrated weaker inner model. **Amended twice**: Amendment 2 rescopes it to L3
  only, because the frozen M4 rule is unsatisfiable at holdout n=4 (arithmetic in
  the amendment). L4/L5.1 move to MVP-3.

---

# MVP plan — pre-registered

> **Outcome (2026-08-11): the MVP terminated at M2 under the frozen headroom rule** —
> baseline 0.917 outside [0.20, 0.85] after the single permitted difficulty revision,
> holdout at ceiling both times. M3/M4 cancelled per protocol; the scorecard was never
> read. See [results.md](results.md) for the full account. The criteria below are preserved
> unmodified as the record of what was frozen.

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

## What "adapts to any model" means — and does not mean

The claim that self-harness "self-adapts to any model" is true of the **mechanism** and
unproven for the **outcome**, and the two must not be conflated:

- **The loop is model-agnostic.** Nothing in rollout → diagnose → propose → select
  assumes a model family. Swap the inner model and the loop re-fits the harness to
  *that* model's failure signatures — the per-model case studies (Qwen → error-triggered
  middleware, MiniMax → forced early delivery, GLM → env persistence) are exactly this:
  same loop, different model, different harness out.
- **The harness produced is model-specific, not universal.** Adaptation *to* any model,
  not a harness *for* all models. Whether a harness evolved for model A helps model B is
  an empirical question (the L5 transfer matrix), and the prior from 2605.30621 is that
  it often will not.
- **Benefit is not uniform.** Harness-benefit is non-monotonic across capability tiers:
  frontier models have little headroom, weak models cannot execute the harness, mid-tier
  gains most. "Adapts to any model" therefore does not imply "helps every model".
- **Unverified.** All of the above is design intent plus published priors. This MVP is
  the first evidence either way for this implementation.

## Model plan — every role on one OpenAI-compatible endpoint

All model calls run on `deepseek-v4-flash` via an OpenAI-compatible proxy
(aihubmix), reached through LangChain's `init_chat_model` with
`model = "openai:deepseek-v4-flash"` and `OPENAI_BASE_URL` pointing at the proxy.
Connectivity, token usage reporting (`prompt_tokens` / `completion_tokens` /
`reasoning_tokens`), and `system_fingerprint` were verified live on 2026-08-11
(fingerprint `fp_a18b46594c_prod0820_fp8_kvcache_20260402`).

| Role | Model | Why |
| --- | --- | --- |
| Outer proposer | deepseek-v4-flash | reasoning model; harness-*updating* ability is roughly flat across model tiers (2605.30621), so a flash-tier proposer is adequate |
| Inner agent | deepseek-v4-flash | harness-*benefit* is non-monotonic across tiers — mid-tier models gain most. A frontier inner agent has little headroom for a harness to add; a mid-tier one is the more sensitive instrument for detecting the effect at all |
| Evaluator | none (deterministic TB2.1 verifiers) | the frozen-evaluator premise stays intact — no LLM judge anywhere in the loop |

What this buys:

- **True "self"-harness.** Proposer and inner agent are the same model: the claim
  being tested is literally self-improvement, not strong-model-tunes-weak-model.
  Cross-model updater→beneficiary cells stay available for L5 (Claude Code as an
  alternate proposer is one function swap away).
- **One accounting stream.** Every token in the experiment flows through one API with
  full usage reporting, so M4's equal-budget comparison is token-matched by
  construction. `reasoning_tokens` are inside `completion_tokens` and are counted —
  a proposer that thinks longer pays for it.
- **Cheap rollouts.** Flash-tier pricing means variance control (repeats, larger N in
  B1) costs little; the budget table below is conservative.

What it costs (each is a registered threat below):

- The provider is a third-party proxy: the model behind the name can drift. Every run
  logs `system_fingerprint`; a fingerprint change **mid-stage** invalidates that stage
  (rerun it), a change **between** stages is recorded in the writeup.
- Temperature and model string are pinned in the config; sampling nondeterminism
  remains and is what `repeats` exists for.

## Stages

### M1 — real-loop smoke (= VERIFY L1)

Toy fixture, live proposer. One to three model calls.

```bash
export DEEPAGENTS_ROOT=...
export OPENAI_API_KEY=<aihubmix key>
export OPENAI_BASE_URL=https://aihubmix.com/v1
# config: model = "openai:deepseek-v4-flash" for both [experiment] and [better_agent]
uv run better-harness run examples/deepagents_example.toml \
  --output-dir runs/m1-smoke --max-iterations 1 --repeats 1
```

M1 additionally confirms the LangChain `openai:` provider path actually honours
`OPENAI_BASE_URL` inside the deepagents proposer — that wiring has been verified only
with raw curl so far.

**M1 status: ✅ executed and verified, 2026-08-11.** deepagents 0.7.5 installed
in-process (no `DEEPAGENTS_ROOT`); proposer = live `openai:deepseek-v4-flash` via
aihubmix. One iteration on the toy fixture, `--repeats 1`. All six criteria checked
mechanically by `scripts/verify_m1.py`:

| Criterion | Result |
| --- | --- |
| Surfaces rewritten by the model | ✅ all four (`prompt`, `tools`, `skills`, `middleware`) |
| Prediction parsed into ledger | ✅ `prediction_made: true` |
| Gate block with real deltas | ✅ conservative, Δ_in=+4 Δ_ho=+4, accepted |
| No `undeclared_surface` violations | ✅ none |
| Proposer token usage recorded | ✅ 201,787 tokens across the proposer transcript |
| `proposal.md` written | ✅ root cause + per-surface rationale |

Prediction grading (first real data point for the L3 methodology): precision 1.0 —
the proposer predicted exactly the four visible train flips and hit all four; recall
0.5 because the four holdout flips are invisible to it, and it correctly listed the
holdout cases under `at_risk` rather than claiming them. Zero unpredicted
regressions. Scores 0/4→4/4 train, 0/4→4/4 holdout, 0/2→2/2 scorecard.

Read this as **liveness, not efficacy**: the toy fixture's failure messages contain
the needed phrases, so a competent proposer should solve it. What M1 establishes is
that the untested path (`invoke_deepagents_proposer` → deepagents → LangChain →
aihubmix → deepseek) works end-to-end, the prompt lands (prediction block emitted
unprompted-by-tests), and token accounting is real. M2 is unblocked.

Pass criteria (none are pass-rate): surfaces actually rewritten (diff vs baseline);
`prediction_made: true` in ledger; `decision.json` has a real gate block; no
`undeclared_surface` guard violations.

**M1 additionally must verify token accounting**: confirm the runner's `summary.json`
contains a usable token/cost field and that `cost.py` reads it. If spend is
unmeasurable, M4 degrades from token-matched to rollout-matched comparison — decide and
record which one the MVP claims **before** M4 runs.

### M2 — task set and baseline variance (= VERIFY L2)

> **Amendment 1 (2026-08-11, recorded before any M2 data was collected).**
> TB2.1-via-harbor is deferred to the post-MVP confirmatory step and M2–M4 run
> instead on a bespoke local agentic suite (`benchmarks/agentic/`). Reasons, decided
> after probing the execution environment: (a) harbor + TB2.1 requires a custom
> harbor agent for editable surfaces to reach the container — upstream only ever
> exercised its harbor runner against a mock, so this is new integration with
> container-level debugging at minutes per rollout; (b) that risk is large enough to
> consume the entire execution budget before producing any M2–M4 evidence.
>
> The amended suite preserves every property the validity audit depends on:
> **real inner agent** (deepagents `create_deep_agent` + live deepseek-v4-flash with
> `temperature=0`, filesystem backend rooted at a per-task sandbox), **deterministic
> frozen verifier** (pytest assertions, no LLM judge), **surfaces genuinely loaded at
> runtime** (prompt/tools/skills/middleware read from workspace files the variant
> overrides), **token accounting** on every rollout.
>
> What it costs, disclosed: (1) **task-designer = experiment-runner** — the 16 tasks
> were authored by the same party running the experiment, with knowledge of the
> harness levers; this is the strongest new bias and is why TB2.1 remains the
> confirmatory step; the tasks were authored and committed **before** the first
> baseline rollout, and may be revised at most once (difficulty only) if the
> baseline lands outside the headroom window below. (2) External comparability is
> zero — no published numbers exist for this suite. (3) Train failure messages
> contain expected values, so a memorising proposer can hard-code visible train
> answers; bounded because M4 judges on the **holdout** margin, which memorisation
> cannot lift, and by the bloat guard. (4) The replaced random-sampling clause is
> void (nothing to sample); stratified split assignment is deterministic
> (alphabetical within stratum: 2 train / 1 holdout / 1 scorecard).
>
> **Headroom window (frozen):** proceed to M3 only if baseline train+holdout pass@1
> is within [0.20, 0.85]. Outside it, one documented difficulty revision is allowed,
> then the window is final. Scorecard files are written by every run as an upstream
> side effect; the unseal-once discipline below is about **reading** them, and
> nothing before the M4 decision may read any scorecard output.

**Task set (amended): 16 authored agentic tasks** — 4 strata × 4 tasks (extraction,
format, multistep, robustness), 8 train / 4 holdout / 4 scorecard, deterministic
verifiers, run by the pytest runner.

> **Difficulty revision 1 (2026-08-11) — the single permitted revision, now spent.**
> Trigger, from the first baseline (runs archived as `runs/*-rev0`): train pass@1
> 0.875, holdout pass@1 **1.000**, zero flaky cases over 5 repeats, B5 identical to
> the seed. Combined 11/12 = 0.917 is above the frozen window ceiling of 0.85, and a
> holdout at 1.0 leaves M4 no margin to detect by construction.
> Revision: all 16 tasks hardened by **compounding exactness requirements**
> (quoted-CSV parsing with discounts, ordinal/two-digit-year dates incl. a leap-year
> trap, multi-key sort orders, conditional checksums, a hint file whose shortcut
> matches the wrong column, NBSP/whitespace normalisation, multi-file edge cases).
> Task ids, strata, and split assignment are unchanged; instructions remain fully
> explicit — difficulty comes from execution discipline, not ambiguity, which is
> precisely the dimension a harness can improve. Per the pre-registration, the
> window is now final: if the revised baseline still lands outside [0.20, 0.85],
> the MVP stops and reports that as its result.

**Original (pre-amendment) task-set text kept for the record:** Terminal-Bench 2.1
subset, 16 tasks (8 train / 4 holdout / 4 scorecard, stratified by task category),
via the harbor runner.

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

One pre-registered exception (see threat 12): if the result is negative, M3+M4 may be
rerun **once** with a frontier proposer (Claude) before the conclusion is written, to
separate "the method fails" from "this proposer fails". Both runs are reported either
way; the exception cannot be invoked twice.

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
8. **Proposer and inner agent are the same model.** Deliberate: it makes the claim
   *self*-improvement rather than distillation. The cost is that the result says
   nothing about cross-model transfer (L5), and a shared blind spot (the model cannot
   see its own systematic failure mode) depresses the result — which biases the MVP
   *against* a false positive, the acceptable direction.
9. **Signature vocabulary untested on TB.** High `unknown` rate expected on first
   contact; it is a measured limitation, not silently absorbed.
10. **Experimenter degrees of freedom.** The main defense is this document's ordering:
    criteria frozen before data, one decision point (M4), one scorecard unseal, and
    negative results are a deliverable, not a bug.
11. **The model behind the proxy is not frozen.** The weights-frozen premise is only
    as good as the provider's routing: aihubmix could silently swap the model behind
    `deepseek-v4-flash`. Mitigation: `system_fingerprint` logged on every call;
    mid-stage change → rerun the stage; between-stage change → reported. Residual
    risk accepted and disclosed — this is the price of the single-API design, and it
    applies equally to both arms of M4, so it threatens absolute numbers more than
    the comparison itself.
12. **Proposer capability floor.** A flash-tier proposer might write weaker harness
    edits than a frontier one. Two reasons this is acceptable at MVP scale: published
    evidence (2605.30621) finds harness-updating ability roughly flat across tiers;
    and if the MVP is positive *despite* a flash proposer, the result is stronger,
    while a negative result triggers one pre-authorized follow-up — rerun M3+M4 with
    a frontier proposer (Claude) before writing the final conclusion, since "the
    method fails" and "this proposer fails" must not be conflated. That follow-up is
    part of the MVP's negative-result protocol, not post-hoc tuning.

## What the MVP deliverable looks like

Either outcome produces the same artifact: a short writeup with the M2 baseline + CI,
the M3 ledger summary (prediction precision vs base rate, unknown rate, guard log),
the M4 comparison with the pre-registered rule applied, and the single scorecard
number. Positive → proceed to L4 multi-seed / L5. Negative → the writeup *is* the
result, and the next question is which box of the loop failed (③ proposals weak? ②
clusters uninformative? ④ gate starved?) — answerable from the same artifacts.

---

# MVP-2 pre-registration

**Registered 2026-08-11, before any calibration rollout.** Purpose: run the
L3 (prediction accuracy), L4 (equal-budget comparison), and L5.1 (locked test)
stages that MVP-1's stop rule correctly cancelled, on the same 16-task suite,
with an inner model that has headroom.

## Roles

- **Proposer (updater):** `openai:deepseek-v4-flash` — unchanged from MVP-1.
- **Inner agent (beneficiary):** selected by the calibration rule below.
- **Disclosure:** proposer and inner agent are no longer the same model. The claim
  under test is *system-level* self-improvement (the agent system edits its own
  harness from its own execution evidence), in the updater≠beneficiary
  configuration that matches AHE practice. Same-model "self" purity was an MVP-1
  property; MVP-2 trades it for a testbed that can detect anything at all.

## Calibration rule (model selection)

1. Candidate models come from the endpoint's inventory, ordered ascending by
   expected capability (list fixed and committed after inventory, before any task
   rollout; every probed candidate is reported).
2. A candidate must first pass a non-task tool-calling smoke (one function call).
3. Calibration baseline: train+holdout at `repeats=3`. First candidate whose
   combined pass@1 lands in **[0.20, 0.85]** is selected. Selection uses baseline
   numbers only — never evolution results — so it cannot favour either M4 arm.
4. The winner's baseline is then re-measured at `repeats=5` (the M4 reference).
5. If the list is exhausted with no candidate in window, MVP-2 stops and reports.

## Frozen experiment parameters

5 iterations · K=1 · `repeats=3` · conservative gate · guards and budget enabled ·
proposer `max_turns=100` · `temperature=0` for the inner agent · suite, split, and
verifiers bit-identical to MVP-1 rev1 (commit `206b916` lineage).

## Decision rules (frozen)

- **L3 read first:** prediction precision vs base rate from `ledger.md`;
  `unpredicted_regressions`; signature `unknown` rate; guard log. Read before any
  pass-rate judgement.
- **M4 (decisive):** B1 = winner-model seed harness, best-of-N, N chosen to match
  the evolution run's **total** spend (inner + proposer tokens; rollout-matched
  reported alongside). Rule: evolution final harness beats B1 on the **holdout
  paired margin by more than the winner's baseline holdout CI half-width**.
  Power disclosure: with 4 holdout cases the margin quantum is 0.25 and the rule
  is hard to satisfy; the pooled train+holdout margin is reported as secondary
  evidence but is not decisive.
- **Scorecard:** unsealed exactly once, after the M4 verdict. Nothing before that
  reads any scorecard output.
- **Fingerprint discipline:** per-rollout `system_fingerprint` is now captured in
  eval summaries; a fingerprint change mid-stage invalidates that stage.
- **No further task revisions of any kind.** The difficulty budget died with MVP-1.

## What MVP-2 can conclude

Positive: on this suite, for this updater→beneficiary pair, one evolution run beat
equal-budget oracle retries — existence, not generality (single seed, authored
tasks, no transfer). Negative: the loop failed to beat retries here — consistent
with published priors, and reported as such. Either way: first L3 prediction-
accuracy data on a non-toy setup.

## MVP-2 calibration list (fixed 2026-08-11, after inventory, before any task rollout)

Ascending expected capability: `qwen3-4b` → `qwen3-8b` → `gpt-4.1-nano` →
`gpt-4o-mini` → `gpt-4.1-mini`. Each must pass a one-call tool smoke first; first
candidate whose repeats=3 train+holdout baseline lands in [0.20, 0.85] is the
MVP-2 inner model. All probes are reported regardless of outcome.

---

## Amendment 2 (2026-08-11, recorded before any M3 or M4 data exists)

**Trigger: the frozen M4 rule is unsatisfiable, and this follows from the M2
baseline alone — no evolution outcome was seen, or exists.**

The reference baseline (`runs/mvp2-baseline`, repeats=5) gives holdout per-case
pass fractions **0.00 / 1.00 / 0.00 / 1.00**, pass@1 0.500, bootstrap CI95
half-width **0.500**. The frozen rule requires the evolution-minus-B1 holdout
paired margin to exceed that half-width, i.e. **margin > 0.500**. The maximum
attainable margin is:

- two of the four holdout cases already pass at 1.00 → no headroom on them;
- the other two fail on all 5 repeats → **B1 oracle pass@N scores them 0 for any
  N**, so B1 = 0.500 exactly, and raising N can only raise B1, never lower it;
- a perfect evolved harness reaches 1.000.

→ **margin ≤ 0.500 for every possible outcome, and the rule demands > 0.500.**
A flawless evolution run fails the test by a strict inequality. The
pre-registration called this "hard to satisfy"; the arithmetic says impossible.
That is a defect in the rule, discovered from data the protocol explicitly
directs M2 to read, and it is recorded here before any M3 rollout.

**Root cause: two goals with an order-of-magnitude difference in power were
bundled into one pre-registration.** L3 (prediction accuracy) is powered by the
number of prediction events — 5 iterations against 7–8 failing train cases. L4
(equal-budget decision) is powered by holdout case count, and needs n ≳ 40 for a
CI half-width near 0.14. n=4 cannot host L4 at any effect size. No 16-task suite
can, for any model.

### What changes

1. **MVP-2 becomes an L3 experiment.** Primary deliverable: prediction precision
   vs base rate, unpredicted regressions, signature `unknown` rate, guard log —
   read from `ledger.md` before any pass rate, as already frozen.
2. **M4 is demoted to descriptive.** B1 still runs and is still reported in full;
   the frozen decision rule is **void** and yields no positive/negative verdict.
   The reason above is the reason, and it may not be replaced by a rule chosen
   after the fact.
3. **L4 and L5.1 move to MVP-3**, which requires its own pre-registration and a
   testbed sized for them (holdout n ≳ 40, tasks selected by measured harness
   sensitivity). See [roadmap](roadmap.md).
4. **Scorecard:** the single unseal still happens once, after M3 and B1 complete,
   and is reported descriptively. The locked-test *claim* is void — both because
   the M4 verdict it was tied to no longer exists and because an aggregate was
   already exposed accidentally ([results](results.md)).

### What does not change

Suite, splits, verifiers, inner model (`gpt-4.1-nano`), proposer
(`deepseek-v4-flash`), 5 iterations, K=1, repeats=3, conservative gate, guards,
budget, `temperature=0`, `max_turns=100`. **No information reaching the proposer
changes.** No task revisions — that budget died with MVP-1.

### Infrastructure changes, disclosed

Made before M3 and after the baseline, so they need stating:

- **Inner-agent retry and per-request timeout.** ~180 rollouts per M3 stage ran
  with no retry at all while only the single proposer call per iteration was
  covered; three M3 attempts died on transport errors. Transport failures now
  retry (5 attempts, 5/10/15/20 s), task failures never do.
  *Comparability:* the baseline campaign recorded **zero** transient transport
  failures (every `result.json` scanned; the only "timeout" strings are the
  `@pytest.mark.timeout(420)` source line echoed in assertion output), so no
  baseline number would have changed under this code. Rollouts now also report
  `attempts`, making any future retry visible rather than silent.
- **Resume (`--resume`).** Reuse is now content-addressed: a stored split result
  is reused only when the variant JSON saved beside it fingerprints identically,
  and a resumed iteration reloads its prior proposal instead of re-asking the
  model. This *fixes* the pre-existing `--reuse-existing` flag, which keyed on
  positional labels (`iter-003`) and would have attributed old numbers to a new
  candidate. Neither behaviour was exercised in any recorded run.

Both are reliability-only: they change which runs *finish*, not what the
proposer sees, what the verifier accepts, or how any decision is made.

---

## Amendment 3 (2026-08-11, recorded after M3 was stopped and voided, before any M3 data is used)

**Trigger: an audit of the instrument, not of the results.** Every recorded
outcome in every run was re-derived from the raw `junit.xml`. Five defects were
found, all reproduced from artifacts before anything was changed; the full
account with numbers is in [results.md](results.md#correction--instrument-defects-found-2026-08-11-and-what-they-change).

**The stopped M3 run is void.** Two independent reasons, either sufficient:
the proposer was receiving all 16 verifier reference implementations — including
all four sealed scorecard cases — on every iteration, so any prediction-accuracy
number would measure the leak rather than the reasoning; and the stage spans two
provider fingerprints, which this pre-registration already says invalidates a
stage. Its artifacts are preserved as evidence, not as results.

### Instrument changes, all recorded before the re-run

| Change | Why it is not a protocol change |
| --- | --- |
| Case-source files shared with a private split are withheld from the proposer | Removes information the proposer was never entitled to. Strictly reduces its inputs |
| Apparatus failures leave numerator and denominator; a mostly-unmeasured evaluation cannot promote | Restores the intended meaning of pass@1. Does not alter the promotion rule for measured evaluations |
| JUnit outcomes resolve by matching configured ids instead of guessing nodeids; the sealed split is evaluated once | Fixes reading the verifier's output. The verifier itself is untouched |
| φ(r) reads the error rather than pytest's echo of the test source; `step_budget_exhausted` and `harness_did_not_load` are named causes | Improves diagnosis quality. Clustering is not part of any decision rule |
| Fingerprint discipline enforced in code | Implements a rule this document already froze |
| Surfaces that do not parse are rejected statically | Extends the existing guard to a defect class that previously cost a full evaluation |

**Unchanged:** suite, splits, verifiers, inner model, proposer, 5 iterations,
K=1, repeats=3, conservative gate, budget, `temperature=0`. MVP-2 remains an
**L3 experiment** with M4 descriptive, per Amendment 2.

### Disclosed asymmetry

The re-run's baseline must be re-measured on the corrected instrument rather
than compared against `runs/mvp2-baseline`. The audit found train and holdout
clean there, so the numbers are expected to reproduce — but "expected to" is not
"verified as", and a baseline measured by a different instrument than the
treatment is exactly the confound this project exists to refuse.

### Registered limitation, not fixed for MVP-2

47% of the measured train+holdout failures are `GraphRecursionError` — the agent
exhausting `RECURSION_LIMIT = 60`, a constant in the frozen inner-agent builder
that **no editable surface can reach**. The proposer can therefore see nearly
half of its failure mass and do nothing about it. Making runtime control policy
an editable surface is the right fix and is a *task-set and surface* change, so
it belongs to MVP-3's pre-registration, not to an amendment of this one. MVP-2's
L3 result must be read with this ceiling stated.
