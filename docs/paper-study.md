# Paper study

Running study notes on papers and methods relevant to self-harness. One entry per
paper: what it claims, what it actually shows, and what this project takes from it.
Append-only; newest at the bottom.

---

## Self-Harness (arXiv 2606.09498) — the namesake paper

*Studied 2026-08-11 from the v1 HTML.*

### Formal setup

Frozen: model M (weights), evaluator ℰ, benchmark protocol, split assignments.
Editable: the harness h — "the non-parametric scaffolding that governs how a fixed
language model is deployed as an agent" (instructions, tools, memory, runtime
policies). Running M under h on task x yields trace τ and output y; outcome
z = ℰ(x, τ, y). Evolution is a lineage h₀, h₁, … with bounded edits Δⱼ(hₜ) = hₜ₊₁.

### Failure signatures (box ②)

φ(rᵢ) = (cᵢ, qᵢ, mᵢ): terminal verifier-level cause / causal status of the agent's
behaviour / abstract mechanism the trace exposes. Clustering is **exact triple
agreement** — deterministic and evaluator-grounded, no fuzzy matching.
(Our `signatures.py` implements exactly this.)

### Promotion rule (box ④)

Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(Δ_in, Δ_ho) > 0 — neither split may regress, at least
one must improve. **No monotonicity theorem is claimed**; "conservative" is a
design description, not a proof. Under stochastic evaluation, pass counts
aggregate across repeats before the rule applies. (Our `gate.py` + `repeats.py`.)

### Editable components

build_system_prompt, memory_sources, subagents, skills, bootstrap / execution /
verification / failure-recovery instructions, runtime control policy (error and
tool-message caps). Proposer edits only declared configuration points, with
**bounded proposal context**: editable surfaces, structured failure patterns,
passing behaviour to preserve, prior edit records.

### Experiments and claimed results

Terminal-Bench-**2.0**, 64-task subset (unstable-web and multimodal excluded).
Minimal DeepAgent-based seed harness. Held-out gains: MiniMax 40.5→61.9%,
Qwen3.5-35B 23.8→38.1%, GLM-5 42.9→57.1%.

### Critical reading — what the numbers do and don't show

1. **No equal-budget baseline.** The comparison is evolved-harness vs seed-harness,
   not vs best-of-N retries at matched spend. Evolution is itself a search that
   consumes many rollouts; without a B1-style arm the headline gains cannot be
   attributed to the *method* over simple test-time scaling (2607.12227's core
   objection stands untouched by this paper).
2. **TB2.0, not 2.1.** The verified 2.1 revision repairs 28/89 tasks. Their 64-task
   cleaning removes some problem tasks, but gains earned against the unrepaired
   set may partly reflect learning to route around broken tasks.
3. **Holdout participates in promotion.** Δ_ho gates acceptance, so held-out is
   validation, not a locked test — repeated access means the final held-out number
   is an optimistic estimate. No third sealed split exists.
4. **Seed is a *minimal* harness.** Gains from a deliberately weak starting point
   overstate what evolution adds to a mature harness (no B5-style arm).

### Often-misread

- **The proposer is the same frozen model M** — self-harness needs no stronger
  external model. (Our MVP-2 deliberately deviates: updater deepseek ≠ beneficiary
  nano, disclosed in the pre-registration.)
- **Model-specific divergence is the headline scientific finding**: identical seed
  harness evolves into different harnesses per model — evidence that harness
  design is inherently model-specific, not generic prompt engineering.

### What this project takes / rejects

Takes: the φ(r) formalism, the conservative gate, bounded proposal context,
repeats-before-gating, model-specific divergence as the framing for "adapts to any
model". Adds what the paper lacks: B1 equal-budget arm, a truly sealed scorecard
split read once, B5 mature-harness baseline, falsifiable prediction ledger, cost
veto, static anti-gaming guard, pre-registered stop rules.

### Authors' admitted limitations

Bounded edits under fixed benchmarks (not open-ended self-improvement); accepted
edits may reflect benchmark-specific failure patterns; dependent on verifier and
trace quality; higher-stakes edits would need stronger acceptance gates than
pass-rate non-regression.

---

## Evo-Bench (arXiv 2608.09096, RUC-AIBox) — a benchmark for harness-evolving capability

*Studied 2026-08-11 from the authors' Chinese write-up. Code: RUCAIBox/Evo-Bench;
data: HF RUC-AIBOX/Evo-Bench; site: evobench.org.*

### What it is

The first unified benchmark measuring a model's **Harness-Evolving Capability**:
long-horizon, code-centric iterative improvement of an executable harness, judged
by generalization to sealed evaluation tasks. Three requirements it enforces that
ad-hoc evaluations miss:

1. **Harness Sensitivity** — tasks must actually respond to harness quality, or
   score changes prove nothing about evolution.
2. **Cross-split Generalization** — validation and evaluation must have *matched
   harness-response distributions*, not just disjoint samples, or gains are
   validation overfitting.
3. **Long-horizon Evolution** — up to 48h / 20 validation iterations / 1,000
   evolver steps of analyze→hypothesize→edit→verify.

### Construction — the principled fix for our MVP-1 failure

**Harness-guided task selection**: 4 frontier models first evolve harnesses on 320
auxiliary tasks (→73 versions →12 representative harnesses); those probe 2,329
candidate tasks to build a Task-Harness Response Map; tasks are kept by
**Sensitivity** (score varies with harness quality) and **Performance** (headroom),
then stratified into 160 validation / 448 sealed evaluation with aligned response
distributions. Final: 608 harness-sensitive tasks across Search (BrowseComp, HLE),
Office (GDPval, APEX-Agents), General (Claw-Eval).

This is the rigorous version of our headroom window: **select tasks by measured
harness-response, not by authored difficulty.** MVP-1 died because our authored
suite had zero measured harness sensitivity (B5 == seed was the tell).

### Protocol — external validation of our MVP-2 shape

Fixed **Policy Model** (main runs: **DeepSeek-V4-Flash** — the same model that
saturated our authored suite scores 29.7 on their seed, confirming our diagnosis
that the task family, not the model, was our problem) + the **Evolver Model**
under test, running in its own fixed evolve-harness. Seed = minimal CodeAct
(shell + final answer only). Evolver sees validation scores/traces only;
evaluation stays sealed until the harness is frozen. **Evolver≠Policy is their
standard configuration** — the updater≠beneficiary split MVP-2 uses.

Two metrics: **Overall Score** (sealed eval, outcome) and **Anytime Validation
Score** (research-process efficiency) — the process/outcome split our ledger
implements at small scale.

### Results

- All 9 evolvers positive from seed 29.7: GPT-5.6-Sol 46.3, Claude Opus 4.8 45.8 —
  still below the human-engineered composite **47.5**.
- Domain-uneven: Search +34.8 (build missing web tools); Office ≈flat or negative
  (specialised file/format workflows resist generic fixes); General 59.4 **beats
  human 56.3** — sometimes by *removing* over-constraints, not adding rules.
- **Early saturation is the norm**: best validated version ≠ final frozen version;
  models misattribute real regressions to noise, skip paired experiments, never
  roll back to historical best. (Exactly the failure classes our conservative
  gate + ledger + at-most-one-promotion are built against.)
- **Budget scaling works** (24h→48h keeps improving both scores) even though most
  models underuse budget — stopping early on stalled reasoning loops.
- **Cross-policy transfer is positive**: harnesses evolved with one policy model
  lift Qwen3.6-35B (13.9→~29) and GLM-5.2 (38.0→48.4) over their own CodeAct
  baselines. Nuances 2606.09498's model-specificity claim: evolved *tooling and
  control structure* transfers; what stays model-specific is thinner than the
  divergence figures suggest.

### Critical read

- Comparison is seed-vs-evolved and human-vs-evolved; **still no equal-budget
  test-time-scaling arm** — the 2607.12227 objection applies here too, though the
  sealed-eval + sensitivity-matched splits close the overfitting half of it.
- Human 47.5 is a composite of three domain-specialised harnesses; the evolvers
  build one general harness — the comparison slightly favours humans.
- Sensitivity selection uses harnesses evolved by frontier models — task selection
  is entangled with what *current* models know how to improve.

### What this project takes

1. **Confirmatory-step upgrade**: Evo-Bench (or its method) is a better external
   testbed than raw TB2.1 for our L4/L5 — purpose-built sensitivity, matched
   splits, sealed eval, public code/data.
2. **Adopt harness-guided task selection** if we ever author tasks again: probe
   with diverse harnesses, keep tasks with measured Sens>0, match split response
   distributions. B5==seed is a cheap one-probe version of this test.
3. Our gate/ledger/rollback design targets exactly the early-saturation failure
   classes they document at scale — independent evidence those mechanisms matter.
4. An **Anytime Validation Score** is worth adding to our reports (best-so-far
   curve over iterations, already derivable from decision.json history).
