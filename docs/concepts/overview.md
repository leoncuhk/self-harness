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

## Project value and intended outcome

The useful product is not merely a better prompt. It is an experimental control plane that converts
harness engineering from anecdotal tuning into a reproducible search process. Given a fixed
beneficiary stack and contract, it should answer four questions:

1. Did behavior improve under an evaluator the optimizer could not edit?
2. Was the gain caused by the harness rather than a stronger model, repaired data route, larger
   budget, evaluator bug, or stochastic retry?
3. Did the gain survive adaptive validation, regression, cost, and latency gates?
4. Can the evidence be replayed, audited, and transferred without importing one benchmark's domain
   assumptions into the generic Controller?

This gives the project practical value even before autonomous evolution becomes strong. It provides
shared infrastructure for controlled Agent experiments, preserves negative results, and prevents
apparatus repairs from being reported as intelligence gains. It also provides the substrate on which
better proposers, acquisition policies, and inner runtimes can be compared under identical rules.

The intended outcome has two stages. First, establish controlled evidence that a structured harness
can improve correctness or efficiency for a fixed task stack. Second, make the outer loop discover
such changes reproducibly and outperform strong human seeds plus equal-budget search baselines. The
first has bounded FAB evidence; the second remains the central open research objective.

## Evidence taxonomy

The project uses distinct names for distinct forms of progress:

- **Apparatus improvement:** fixes execution, telemetry, evaluator, or frozen data validity. It
  increases confidence in measurements, not task capability.
- **Human-directed harness improvement:** a matched control supports harness value, but not
  autonomous search value.
- **Autonomous candidate improvement:** the proposer generates a change that clears the frozen
  promotion contract on replicated train and adaptive validation.
- **Search-method value:** autonomous evolution beats strong zero-evolution and equal-total-budget
  retry or Best-of-N.
- **Generalization and compounding:** a sealed scorecard, new domains or models, and later generations
  demonstrate increasingly stronger claims.

Software correctness is therefore necessary but never substituted for efficacy. A green suite
establishes that the experiment can be trusted to run; only controlled task outcomes establish that
the harness or search method works.

## What transfers across domains

The reusable object is not a universal prompt or one preferred Agent framework. It is the protocol:

```text
frozen objective + domain contract + inner artifact contract + external evaluator + promotion gate
```

The Controller, archive, budgets, split isolation, guards, and monotone selection are domain-neutral.
A vertical supplies its task runtime, typed evidence artifacts, public diagnostic vocabulary, and
frozen evaluator. FAB contributes source-period provenance and accounting invariants; coding
contributes product diffs and CI failures; experimental science might contribute units, calibration,
and physical measurements. Those concepts must not leak into one another's default proposer prompt.

This yields a useful design test: adding a vertical should primarily add benchmark contracts and
adapters. If it requires editing the gate or generic trace logic, the abstraction boundary is
probably wrong.

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
- A better diagnosis vocabulary can reduce wasted search but is not itself improvement. Only a
  candidate that clears frozen train, adaptive-validation, cost, and regression gates is evidence of
  harness efficacy.
- The current FAB hard-4 result establishes bounded human-directed harness value. It does not raise
  the autonomous outer loop beyond integration and correct rejection because Pi did not discover
  the accepted mechanisms.

## Scientific claim language

Use: “best validated candidate found under contract X, model Y, splits Z, and budget B.”

Do not infer from a smoke run: global optimum, official FAB rank, stable multi-generation compounding,
cross-model transfer, or superiority over equal-budget retry. Those require separate measurements.

Primary design influences: Self-Harness (failure signatures and monotone promotion), Agentic Harness
Engineering (trajectory observability and structural surfaces), autoresearch/AlphaEvolve (external
fitness and archives), and evaluation work emphasizing sealed tests and equal-compute comparisons.
