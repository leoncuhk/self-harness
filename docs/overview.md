# Self-harness: concept and evidence base

*The distilled cognition layer. Full research notes: [`archive/plan-2026-08.md`](archive/plan-2026-08.md).*

## Definition

**Model weights frozen. Evaluator frozen. The harness is the only writable surface —
edited by the system itself from its own execution evidence, validated by task
outcomes.** Not "making the model smarter"; making the engineering layer around a
fixed model improve automatically.

The claim "adapts to any model" is true of the mechanism and unproven for the
outcome: the loop is model-agnostic, the harness it produces is model-specific, and
whether adaptation *helps* is non-uniform across capability tiers.

## First-principles map

Autoresearch, LLM Wiki, AlphaEvolve/ShinkaEvolve, self-harness, and parts of
recursive self-improvement share one substrate:

```text
state -> propose mutation -> execute in environment -> external evaluation
      -> select -> retain evidence/state -> repeat
```

What distinguishes them is not the loop but the **mutable state** and the
**source of truth**. Autoresearch mutates experiment code and hyperparameters;
LLM Wiki mutates a synthesized knowledge artifact while source material remains
fixed; evolutionary systems mutate programs or algorithms under task fitness;
self-harness mutates the engineering layer around a frozen beneficiary model.
Weight training changes the model policy itself and belongs to a stronger class.

The compact equation is `improvement = search × criterion`. Proposal, execution,
selection, and memory can often be automated. Evaluation can also be executed
automatically, but its *validity* cannot be certified solely by the optimizer it
judges: the loop still needs an anchor it cannot rewrite, such as formal proof,
physical measurement, frozen tests, private data, or human governance. Evaluators
may themselves be improved, but only against a higher-level meta-evaluation; this
moves the external boundary rather than removing it.

Recursive self-improvement is therefore related but not synonymous. A frozen
model editing its prompt or tools is recursive artifact improvement (L3 here).
It becomes stronger RSI only when the improved system reliably improves its own
future improvement process and the gains compound under controlled evaluation.
One successful edit, repeated search, or a higher benchmark score does not by
itself demonstrate recursion or compounding.

## The loop

Every self-harness method is an instance of one loop:

```
┌─────────┐    ┌──────────┐    ┌─────────┐    ┌────────┐
│ ①Rollout │ →  │ ②Diagnose │ →  │ ③Propose │ →  │ ④Select │ ─┐
└─────────┘    └──────────┘    └─────────┘    └────────┘  │
     ↑                                                     │
     └─────────────────────────────────────────────────────┘
```

| Method | ② Diagnose | ③ Propose | ④ Select |
| --- | --- | --- | --- |
| DGM | eval traces | code self-edit | archive / diversity |
| SICA | benchmark scores | agent edits own codebase | greedy best |
| ACE | execution feedback | context/playbook delta | incremental merge |
| Self-Harness (2606.09498) | failure signatures φ(r)=(c,q,m) | targeted harness edit | conservative monotone: Δ_in≥0 ∧ Δ_ho≥0 ∧ max>0 |
| AHE (2604.25850) | trajectory-level error attribution | edit + falsifiable prediction | outcome vs prediction |
| TTHE (2607.08124) | unlabelled batch traces | N proposers, one objective each | agentic judge picks one |
| Meta-Harness | multi-objective scores | harness program search | Pareto front |
| **this repo** | φ(r) over assertion text | 1–K candidates + prediction | conservative gate + cost veto |

Capability levels: **L0** prompt → **L1** context/memory → **L2** workflow/graph →
**L3** harness self-edit → **L4** self-referential (edits its own editor) → **L5**
joint weights+harness. This project operates at L3.

## What the evidence actually says (priors to respect)

- **Harness engineering works; automated self-harness is unproven.** LangChain's
  +13.7pt (52.8→66.5) was human-in-the-loop. The best automated public number is
  NVIDIA's +2/127. Nobody should conflate the two.
- **Harness-updating ability is roughly flat across model tiers; harness-benefit is
  non-monotonic** (2605.30621) — frontier models have little headroom, weak models
  can't execute the harness, mid-tier gains most. Corollary learned the hard way in
  MVP-1: *tier labels track price, not capability on your task distribution*.
- **Equal-budget comparison is mandatory, and the evidence is mixed.** One
  Terminal-Bench 2.1 study (2607.12227) reports evolution below parallel sampling
  without unit tests (67.4 vs 72.3) and below sequential refinement with unit
  tests (86.2 vs 91.8), with only +0.6pp held-out transfer. Other structural
  evolution systems report gains over token-matched sampling. The safe conclusion
  is not that evolution always loses or wins: on deterministic-verifier suites,
  sequential refinement and best-of-N are required comparators, and structural
  evolution earns its claim only when it beats them at matched total spend.
- **What does produce gains is structural, not prose** (2604.25850): TB2 69.7→77.0,
  above human-engineered Codex-CLI, with the ablation localising the gain to
  **tools, middleware, and long-term memory — not the system prompt**; transfer
  holds cross-family (+5.1–10.1pp) and to SWE-bench-verified at 12% fewer tokens.
  Every positive result of this kind feeds the proposer **execution traces**.
- **Benchmark hygiene is load-bearing**: Terminal-Bench 2.1 repairs 28 of 89 tasks
  from 2.0 (dependency drift, budget mismatches, instruction/test misalignment).
  Evolving against a broken benchmark teaches routing around broken tasks.
  Stronger form (Evo-Bench, 2608.09096): select tasks by **measured harness
  sensitivity**, and match the response distribution across splits.

**Synthesis of the 2026 literature:** the positive results all come from
trace-grounded diagnosis over structural surfaces; the negative results all come
from honest budget matching. No published work has both at once. That gap is
this project's position — see the [roadmap](roadmap.md).

## What would make self-harness "proven"

1. An evolution run beats the **strongest** equal-budget test-time-scaling arm on
   validation — best-of-N, and sequential refinement wherever a deterministic
   verifier makes it available — by a margin above baseline noise, reproduced
   across seeds (L4 of the [verification ladder](verification.md)).
2. The gain survives a locked test set read once, is not concentrated in 2–3
   tasks, and transfers across models/benchmarks (L5).
3. The proposer's predictions beat the base rate — evidence it is engineering,
   not searching (L3).

Any of these failing is a reportable result, not a reason to keep tuning.

## References

Full critical reads in [paper-study.md](paper-study.md); this is the index.

| | Paper | Why it matters here |
| --- | --- | --- |
| Method | Self-Harness **2606.09498** | the namesake: φ(r), conservative gate, bounded context |
| Method | AHE **2604.25850** | strongest positive result; 3 observability pillars; prompt-is-not-the-lever ablation |
| Method | TTHE **2607.08124** | test-time evolution, multi-objective proposers, transductive-scoring caveat |
| Method | Meta-Harness **2603.28052** (code: stanford-iris-lab/meta-harness) | harness program search, Pareto selection |
| Evidence | Tier study **2605.30621** | updating ability flat, benefit non-monotonic |
| Evidence | Evaluation critique **2607.12227** | the falsifier: evolution loses at equal budget |
| Bench | Evo-Bench **2608.09096** | harness-sensitivity task selection, sealed eval, matched splits |
| Bench | SEAGym **2606.17546** · Terminal-Bench 2.1 / harbor | alternate testbeds |
| Boundary | EvoHarness-RL **2608.05446** | learned runtime access policy — breaks frozen weights (L5) |
| Survey | Lil'Log 2026-07-04 · RUCAIBox `awesome-agent-harness` | field map; the four requirements for a credible setup |
| Practice | LangChain harness engineering blog · deepagents (langchain-ai) | the human-in-the-loop reference point |
