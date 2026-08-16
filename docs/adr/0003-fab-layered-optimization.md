# ADR 0003: Layer FAB optimization around typed evidence

- Status: accepted
- Date: 2026-08-16

## Decision

Optimize FAB as a layered finance system, not as unconstrained prompt search. Before proposing a
harness mutation, route observed failures across six layers:

1. beneficiary-model capability;
2. frozen data-plane availability and reproducibility;
3. research and orchestration;
4. finance semantics and deterministic computation;
5. verification and accounting invariants;
6. answer compilation and materialization.

Only layers 3–6 are evolvable during one experiment contract. A capability or frozen data-plane
failure produces a diagnostic no-op and a request for a new experiment contract; it must not be
disguised as another prompt improvement.

The inner runtime should move information through typed artifacts: an obligation list, source and
period provenance, an evidence ledger, a deterministic calculation ledger, invariant results, and
an answer manifest. Markdown surfaces tell the model how to produce them, while host-owned tools,
schemas, snapshots, and the evaluator establish their meaning. An Agent framework may orchestrate
this flow, but is replaceable.

Use multi-fidelity selection: cheap train smoke, adaptive validation for candidates that clear the
train floor, replicated confirmation for finalists, then one sealed scorecard read. Compare the
winner against a strong human seed and equal-total-budget retry/Best-of-N before claiming search
value.

## Evidence

The Public-24 evolution run evaluated six Pi proposals under a fixed DeepSeek+Prime stack and
promoted none. A GPT-5.6-sol+Codex diagnostic solved three of four previously stuck cases, showing
that many failures were beneficiary-stack limitations rather than missing prompt rules.

q025 remained wrong under both native and strong-harness Codex. A human-directed diagnostic series
then isolated four reusable mechanisms: actual-versus-guidance period provenance, deterministic SEC
attachment routing, FCFF noncash reconciliation, and explicit subtotal/sign materialization. The
result passed q025 at 1.000 in three independent repeats. It did not pass the global no-regression
gate because q013 fell from its prior pass under a varying external price route. This jointly shows
that layer-specific harness changes can work and that an unfrozen data plane prevents trustworthy
global promotion.

## Consequences

- `diagnostic_facets` are deterministic routing hints, not asserted root causes. The proposer must
  state a causal layer and select the smallest relevant surface.
- SEC filings, market prices, and other evaluation inputs should come from a versioned host service
  or immutable snapshot with recorded content hashes. Agent-sandbox networking is not an adequate
  experimental data plane.
- Prime and Codex are formal FAB inner adapters and Pi is the current atomic proposer. Codex is the
  measured best beneficiary stack. None is part of the domain-independent architecture.
- q025 v5 stays experimental until replicated train and adaptive-validation controls pass under one
  frozen data plane. A successful training case is not a globally promoted harness.
- Bayesian or LLM-guided acquisition becomes useful only after enough comparable candidates exist;
  it does not repair weak measurements or replace the promotion gate.
