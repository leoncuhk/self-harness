# Architecture

## Ownership boundary

```text
                         immutable control plane
        goal / splits / evaluator / budget / permissions / audit
                                  │
                                  ▼
product task ──> inner agent ──> answer/code + full telemetry ──> frozen evaluation
                    ▲                                             │
                    │                                             ▼
              current harness                         layered failure evidence
                    ▲                                             │
                    └── outer loop: diagnose → propose → experiment → promote/reject
```

The upper row is an ownership boundary, not an instruction prompt. Only the Controller promotes a
candidate. No runtime or proposer can change the goal, task
assignment, evaluator, model route, inference budget, data plane, resource gate, scorecard, or
historical archive. Prime, Codex, and Pi are adapters, not architectural authorities.

The system has four intentionally small planes:

| Plane | Stable responsibility | Replaceable input |
|---|---|---|
| Control | freeze, execute, compare, promote, archive | experiment configuration |
| Domain | name failure layers and interpret public telemetry | diagnostic contract |
| Execution | solve one task and emit typed artifacts | inner runtime and harness surfaces |
| Evaluation | measure the product independently | frozen evaluator and data snapshot |

This decomposition is the portability boundary. A new vertical supplies domain, execution, and
evaluation contracts; it does not fork the Controller.

## Readiness and failure layers

Harness search starts only after the fixed beneficiary stack and frozen data plane can execute a
representative task. Every measured failure is then routed to capability, data plane,
research/orchestration, domain semantics/computation, verification, or answer compilation.
Deterministic `diagnostic_facets` expose observed cross-layer signals; they do not prove causality.
Domain-specific facets are declared in a frozen TOML profile and included in the evaluation
fingerprint. The generic core retains only operational facets that have the same meaning across
domains.

Capability and data-plane failures are outside candidate surfaces. The correct outcome is a no-op
and a new experiment contract or apparatus repair. Search may change only the declared harness
surfaces that causally affect the four downstream layers. This prevents spending iterations on
prompt prose when the model cannot perform the task or the required source is unavailable.

## Inner loop

Each rollout starts from a private harness snapshot and fresh agent process. FAB has two formal inner
adapters. Prime is the lower-cost research baseline with persistent IPython state, optional
`rlm(...)` specialists, and a reserved no-tool compiler. Codex is the current high-capability path
and measured best stack. The experiment selects either adapter through a fingerprinted environment
field; both return the same answer and telemetry contract to the frozen evaluator. Prime supports
host-enforced time/token/turn ceilings. Codex currently supports a host-enforced wall-time ceiling
and post-run token accounting, so a Codex experiment must not claim a hard token/turn cutoff.

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
disabled. It reads the experiment's diagnostic contract rather than a global finance prompt and
returns one JSON object containing:

- a root-cause claim and evidence;
- predicted pass flips and regression risk;
- complete replacement text for declared changed surfaces.

Parsing and application are atomic. Invalid JSON, partial output, empty surface text, or undeclared
surface names cause rejection before any rollout. This task is a constrained transformation, so an
open-ended coding-agent file loop adds cost and failure modes without useful capability.

## Selection

A candidate must pass static path/leak/syntax/growth guards, improve the primary objective by the
frozen floor, avoid pass and constraint regressions, and remain inside cost/latency ceilings.
Publication-grade contracts additionally match incumbent and candidate by question, resample
question clusters, and require the family-wise confidence interval to clear the effect floor on
adaptive validation. The correction uses the maximum candidate comparisons declared before the run;
the optimizer cannot gain significance by silently trying more variants. At most one candidate is
provisionally promoted per generation.

Matched questions are not claimed to be paired hidden randomness. Repeats remain independent model
executions unless a provider exposes a reliable seed. The estimate therefore reports question-level
uncertainty and provenance honestly rather than manufacturing stronger causal language.

The scorecard is unavailable to the proposer and does not participate in adaptive selection. Because
validation is consulted repeatedly, it is called adaptive validation rather than an untouched
holdout. Every decision, rejected candidate, prediction, resource measurement, and lineage edge is
retained for replay.

An adaptive-validation winner is a **provisional promotion**. A **confirmed release** additionally
requires the pre-registered replicated confirmation/scorecard protocol. This distinction prevents a
run-local winner from being presented as a publication result.

A reported search win also needs a strong zero-evolution baseline and an equal-total-budget
retry/Best-of-N arm. Otherwise an apparent evolutionary gain may be ordinary stochastic resampling.

## Security and causality

Private workspaces and allowlisted surfaces protect attribution, not host security. A production
deployment must additionally use a container/VM sandbox, least-privilege secrets, egress policy, and
an evaluator service the agent process cannot modify.
