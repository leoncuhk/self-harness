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
| AHE | error attribution | 7 components + 4 commitment fields | outcome + flip attribution |
| Meta-Harness | multi-objective scores | harness program search | Pareto front |

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
- **Automatic harness evolution does not consistently beat equal-budget test-time
  scaling, and generalizes poorly to held-out tasks** (2607.12227). The decisive
  comparison is always evolution vs. best-of-N retries at equal spend, and the
  expected outcome is a loss.
- **Benchmark hygiene is load-bearing**: Terminal-Bench 2.1 repairs 28 of 89 tasks
  from 2.0 (dependency drift, budget mismatches, instruction/test misalignment).
  Evolving against a broken benchmark teaches routing around broken tasks.

## What would make self-harness "proven"

1. An evolution run beats equal-budget best-of-N on validation, margin above
   baseline noise, reproduced across seeds (L4 of the [verification ladder](verification.md)).
2. The gain survives a locked test set read once, is not concentrated in 2–3
   tasks, and transfers across models/benchmarks (L5).
3. The proposer's predictions beat the base rate — evidence it is engineering,
   not searching (L3).

Any of these failing is a reportable result, not a reason to keep tuning.

## References

- Self-Harness: arXiv 2606.09498 · Meta-Harness: arXiv 2603.28052 (code: stanford-iris-lab/meta-harness)
- Tier study: arXiv 2605.30621 · Evolution vs test-time scaling: arXiv 2607.12227
- LangChain harness engineering blog · deepagents (langchain-ai) · Terminal-Bench 2.1 / harbor
