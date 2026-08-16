# Architecture

## Ownership boundary

```text
┌───────────────────────────────────────────────────────────────┐
│ Frozen Self-Harness Controller                                │
│ goal · splits · model · budgets · evaluator · guards · gate   │
│ run candidates · aggregate telemetry · archive · select       │
└──────────────────────────────┬────────────────────────────────┘
                               │ bounded visible train evidence
                    ┌──────────▼──────────┐
                    │ Outer Proposer     │
                    │ diagnose one layer │
                    │ JSON patch + claim │
                    └──────────┬──────────┘
                               │ validated declared surfaces
┌──────────────────────────────▼────────────────────────────────┐
│ Evolvable Inner Runtime                                       │
│ obligations → evidence/provenance → calculations/invariants   │
│ orchestrator · specialists · verification · answer compiler   │
└──────────────────────────────┬────────────────────────────────┘
                               │ answer/product diff + telemetry
                    ┌──────────▼──────────┐
                    │ Frozen Evaluator   │
                    └────────────────────┘
```

Only the Controller promotes a candidate. No runtime or proposer can change the goal, task
assignment, evaluator, model route, inference budget, data plane, resource gate, scorecard, or
historical archive. Prime and Pi are current adapters, not architectural authorities.

## Readiness and failure layers

Harness search starts only after the fixed beneficiary stack and frozen data plane can execute a
representative task. Every measured failure is then routed to capability, data plane,
research/orchestration, finance semantics/computation, verification, or answer compilation.
Deterministic `diagnostic_facets` expose observed cross-layer signals; they do not prove causality.

Capability and data-plane failures are outside candidate surfaces. The correct outcome is a no-op
and a new experiment contract or apparatus repair. Search may change only the declared harness
surfaces that causally affect the four downstream layers. This prevents spending iterations on
prompt prose when the model cannot perform the task or the required source is unavailable.

## Inner loop

Each rollout starts from a private harness snapshot and fresh agent process. FAB currently uses
Prime because the task benefits from persistent IPython state and optional `rlm(...)` specialists;
another runtime is valid if it satisfies the same artifact and budget contract. The host enforces
time/token/turn ceilings, attributes child usage, persists full telemetry, and reserves a separate
no-tool compiler so a research cutoff does not force an empty answer.

The target FAB inner flow is structured rather than a free-form research transcript:

1. compile every requested output, period, unit, and source obligation;
2. retrieve from a versioned host-owned source and record source/period provenance;
3. calculate through deterministic tools and retain inputs, formulas, units, and signs;
4. test domain invariants such as FCFF noncash reconciliation and bridge identities;
5. materialize every required number and subtotal in the final answer;
6. let the frozen evaluator score the answer and retain complete telemetry.

Markdown policies are evolvable guidance. Schemas, data snapshots, calculation semantics, and the
evaluator are frozen control-plane assets. This is the boundary that turns fluent research into a
reproducible financial workflow.

For coding projects, the runner creates a disposable product checkout, lets the inner agent modify
only product files, and runs CI outside the agent. Product changes never mutate the harness source.

## Outer loop

The Controller normalizes visible failing traces, adds non-causal diagnostic facets, clusters failure
mechanisms, and builds one bounded context containing only task instructions, normalized experience,
failure clusters, and current surfaces. The current Pi adapter receives that context with all tools
disabled and returns one JSON object containing:

- a root-cause claim and evidence;
- predicted pass flips and regression risk;
- complete replacement text for declared changed surfaces.

Parsing and application are atomic. Invalid JSON, partial output, empty surface text, or undeclared
surface names cause rejection before any rollout. This task is a constrained transformation, so an
open-ended coding-agent file loop adds cost and failure modes without useful capability.

## Selection

A candidate must pass static path/leak/syntax/growth guards, improve the primary train objective by
the frozen floor, avoid pass and constraint regressions, remain inside cost/latency ceilings, and
satisfy the same rule on adaptive validation. Cheap train smoke precedes validation; replicated
confirmation is required for a finalist. At most one candidate is promoted per generation.

The scorecard is unavailable to the proposer and does not participate in selection. Because
validation is consulted repeatedly, it is called adaptive validation rather than an untouched
holdout. Every decision, rejected candidate, prediction, resource measurement, and lineage edge is
retained for replay.

A reported search win also needs a strong zero-evolution baseline and an equal-total-budget
retry/Best-of-N arm. Otherwise an apparent evolutionary gain may be ordinary stochastic resampling.

## Security and causality

Private workspaces and allowlisted surfaces protect attribution, not host security. A production
deployment must additionally use a container/VM sandbox, least-privilege secrets, egress policy, and
an evaluator service the agent process cannot modify.
