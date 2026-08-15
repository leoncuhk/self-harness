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

---

## Rethinking the Evaluation of Harness Evolution (arXiv 2607.12227) — the falsifier

*Studied 2026-08-11. Cited across this repo as the decisive prior; recorded here in full.*

### The framework

Four methods compared under one budget protocol, on **Terminal-Bench 2.1** (89
tasks) with Claude Opus 4.6 / GPT-5.4 / GPT-5.4-mini, averaged over two runs:

| Method | What it spends budget on |
| --- | --- |
| Parallel sampling | K independent trajectories, pick by verifier or self-judgment |
| Sequential refinement | iterative depth — refine the prior attempt |
| Harness evolution | meta-agent optimises the harness across task batches |
| Harness scaling | per-instance harness adaptation from task feedback |

Two budget axes held equal: **feedback budget** (what correctness signal each
method may read — unit tests vs self-judgment) and **inference budget** (K=5).
Separating these two is the contribution; most prior work matches neither.

### Results

| Condition | Best test-time scaling | Harness evolution |
| --- | --- | --- |
| No unit tests | parallel sampling **72.3** (from 68.2 baseline) | **67.4** — *below baseline* |
| With unit tests | sequential refinement **91.8** (pass@5) | **86.2** |
| Held-out tasks | — | **+0.6pp** average gain |

### What this project takes

1. **B1 alone is not enough.** Our decisive arm is parallel/oracle best-of-N. On
   a suite with deterministic verifiers — which is exactly our situation — their
   strongest arm is **sequential refinement**, and it beats evolution by 5.6pp.
   An evolution run that clears B1 but was never tested against refinement has
   not cleared the bar this paper sets. Registered as a gap ([roadmap](../development/roadmap.md) F1).
2. **The +0.6pp held-out figure is the number to beat**, and it is the reason our
   scorecard is sealed rather than merely held out.
3. Their two-axis budget definition is sharper than ours: our M4 rule matches
   total tokens (inference) but never states the **feedback** budget explicitly.
   B1 retries read pass/fail per attempt; evolution reads per-case failure
   messages. Those are not the same feedback, and the writeup must say so.

---

## Agentic Harness Engineering (arXiv 2604.25850) — the strongest positive result

*Studied 2026-08-11 from the abstract page.*

### Method

Three observability pillars, and the vocabulary is worth adopting wholesale:

| Pillar | What it means | Our status |
| --- | --- | --- |
| **Component** observability | file-level representations of every editable harness part | ✅ `surface_manifest.json` |
| **Experience** observability | trajectory data distilled into evidence the proposer can consume | ❌ **missing** — we pass pytest assertion text only |
| **Decision** observability | every edit paired with a prediction, verified against outcomes | ✅ `ledger.json` (built independently, same shape) |

"Every edit becomes a falsifiable contract" — the same premise as our P2-6 ledger.

### Results

TB2 pass@1 **69.7 → 77.0** over ten iterations, above the human-engineered
Codex-CLI (71.9) and above self-evolving baselines ACE and TF-GRPO. Transfer to
SWE-bench-verified: same aggregate success at **12% fewer tokens**. Cross-family:
**+5.1 to +10.1pp** across three model families.

### The ablation that should redirect our surface design

Gains localise to **tools, middleware, and long-term memory — not the system
prompt.** Structural harness elements transfer; prose-level strategy does not.

Our four surfaces are prompt / tools / skills / middleware: two of the three
productive categories are present, **long-term memory is absent entirely**, and
the least productive surface (prompt) carries the most weight in our seed. See
[roadmap](../development/roadmap.md) C.

### Critical read

Seed-vs-evolved and vs-human comparisons; no equal-budget test-time-scaling arm
here either. The transfer results are the load-bearing evidence, not the 77.0.

---

## TTHE — Test-Time Harness Evolution (arXiv 2607.08124)

*Studied 2026-08-11.*

Evolves the harness **during evaluation** from unlabelled traces. Per batch:
observe (full traces — prompts, tool calls, errors, outputs) → multiple proposer
agents each rewrite the harness toward a **different improvement objective** →
an agentic judge commits one version for the next batch. Solver, proposers, and
judge are all the same frozen LLM under different harnesses.

Results: BIRD text-to-SQL 12→50, competitive programming 30→38.3, SWE 20→35.
Evolved harnesses discovered grounding, verification, and repair strategies **as
executable code**, not prompt prose — consistent with AHE's ablation.

**Critical read (their own):** scoring is **transductive** — a harness adapts on
a batch and is scored on that same batch. Forward generalisation is unproven;
they name **prequential** evaluation (score batch *t*'s harness on batch *t+1*
before it adapts) as the missing test.

What this project takes: (1) **multi-objective proposers** are a better K>1
design than our cluster round-robin — diversity by objective, not by cluster
index; (2) prequential scoring is a structurally cheap addition for us and an
open gap in the literature ([roadmap](../development/roadmap.md) E3, F2).

---

## EvoHarness-RL (arXiv 2608.05446) — the boundary case

*Studied 2026-08-11.*

Trains the model to use runtime scaffolding, via SFT then cost-aware GRPO.
Harness abstracted to a **BPE** interface — Belief (environment state), Progress
(subgoal status), Experience (cross-episode skills) — reachable through four
meta-actions: `track`, `commit`, `recall`, `note`. ALFWorld, Qwen3-8B: 96.9%
seen / 86.6% unseen, matching Claude Opus 4.5; each BPE component worth 6–8pp.

Two dynamics worth naming: **harness annealing** (training internalises the
scaffold — ~5 calls/episode → ~1, keeping only high-value external access) and
**experience consolidation** (the store compacts by forgetting, rather than
growing append-only).

Relevance is as a **boundary marker, not a method to adopt**: it breaks our
frozen-weights premise (this is L5 joint weights+harness). It also states the
comparison we should expect to face — prompt-level scaffolding scored 56.4% vs
96.9% for a learned access policy, i.e. *when* to use the harness may matter more
than *what* the harness says. Our runtime-policy surface gap ([roadmap](../development/roadmap.md) C2)
is the frozen-weights version of that lever.

---

## Shorter entries

**SEAGym (arXiv 2606.17546)** — evaluation environment for self-evolving agents
across SWE / web / tool-use domains, measuring learning trajectories rather than
static scores, with a train/test protocol against benchmark overfitting. Reports
**catastrophic forgetting** as the persistent failure. A candidate external
testbed, below Evo-Bench in priority (less harness-specific).

**Lil'Log, "Harness Engineering for Self-Improvement" (2026-07-04)** — the survey
that names the optimisation ladder: prompt → structured context → workflow →
harness code → **optimizer code** (our L0–L4 under other names). Four
requirements for a credible setup: observability, read-only evaluator access,
evidence-grounded edits with predicted at-risk regressions, and **logging
rejected candidates and negative results instead of discarding them**. We satisfy
the middle two; observability is partial (component+decision, no experience) and
**negative-result reuse is absent** — rejected candidates are written to
`decision.json` but never fed back into the proposer's context ([roadmap](../development/roadmap.md) B4).
Seven named bottlenecks, of which diversity collapse and reward hacking are the
two our K-candidate and guard designs touch.

**RUCAIBox, "Agent Systems with Harness Engineering"** (survey + `awesome-agent-harness`)
— field map: harness evolution, design (workflow / memory / skills / multi-agent),
model adaptation, benchmarks by domain, future directions. Use as the index when
looking for a domain-specific benchmark; not a source of claims.
