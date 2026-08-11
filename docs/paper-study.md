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
