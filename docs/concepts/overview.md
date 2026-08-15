# Self-harness from first principles

## One common substrate

Autoresearch, LLM Wiki, AlphaEvolve/ShinkaEvolve, self-harness, and stronger recursive-improvement
systems share a closed-loop substrate:

```text
state -> propose mutation -> execute -> measure externally -> select -> retain evidence -> repeat
```

They differ in what is mutable. Autoresearch changes experiment code and hyperparameters; LLM Wiki
changes a synthesized knowledge artifact while source material stays fixed; AlphaEvolve-style
systems change programs; self-harness changes prompts, workflow, tools, memory, delegation, and
verification around a frozen beneficiary model. Weight training changes the beneficiary policy
itself and is a stronger class.

The compact equation is `improvement = search × criterion`. Proposal, execution, selection, and
memory can be automated. Evaluation can be executed automatically too, but the optimizer cannot be
the sole authority on whether its own evaluator remains valid. A credible loop therefore has an
external anchor it cannot edit: frozen tests, formal proof, private data, physical measurement, or
human governance.

## Relationship to recursive self-improvement

Self-harness is recursive artifact improvement: the system changes machinery that shapes its own
future behavior. It is not automatically strong recursive self-improvement. That stronger claim
requires controlled evidence that an improved system becomes better at producing further
improvements and that gains compound across generations. One accepted edit, repeated search, or a
higher benchmark score is insufficient.

## Why two loops

The inner loop solves the actual task: for coding, edit product code and run CI; for FAB, research,
calculate, verify, and submit. The outer loop changes the policy and machinery that the inner agent
uses. Keeping their workspaces and evaluators separate makes score changes attributable and permits
independent rollback.

The human belongs at the criterion/governance boundary, not in routine proposal generation. Human
review can improve safety and evaluator validity, but must not silently tune the same scorecard later
reported as untouched.

## What current evidence supports

- Harness engineering can materially change frozen-model behavior.
- Automated harness search is credible only with trace-grounded diagnosis, structural editable
  surfaces, protected evaluation, and equal-budget comparators.
- Validation used repeatedly for selection becomes adaptive development data, not an untouched
  holdout. A scorecard must remain sealed until the protocol permits one final read.
- Frozen-weight harness evolution changes the behavior distribution but does not prove weight-level
  learning or compounding RSI.
- LLM-guided Bayesian optimization, including region-lifted preferences, is relevant as a future
  acquisition policy when evaluations are expensive. It can guide which candidate to test, but it
  does not replace the frozen evaluator or causal gate and is unnecessary at the current small
  discrete search scale.

## Scientific claim language

Use: “best validated candidate found under contract X, model Y, splits Z, and budget B.”

Do not infer from a smoke run: global optimum, official FAB rank, stable multi-generation compounding,
cross-model transfer, or superiority over equal-budget retry. Those require separate measurements.

Primary design influences: Self-Harness (failure signatures and monotone promotion), Agentic Harness
Engineering (trajectory observability and structural surfaces), autoresearch/AlphaEvolve (external
fitness and archives), and evaluation work emphasizing sealed tests and equal-compute comparisons.
