# Architecture: Prime execution inside a frozen controller

## System claim

This project optimizes a coding-agent harness. It does not claim to find a
global optimum. A run produces the best validated harness found under a frozen
goal contract and a recorded resource budget.

The implemented topology is:

```
┌──────────────────────────────────────────────────────────────┐
│ Self-Harness Controller                                      │
│ frozen goal/splits/model/budget/evaluator → run → gate       │
└──────────────────────────────┬───────────────────────────────┘
                               │ visible train evidence
                    ┌──────────▼──────────┐
                    │ Prime Outer Proposer│
                    │ diagnose + edit only│
                    │ declared surfaces   │
                    └──────────┬──────────┘
                               │ candidate harness
┌──────────────────────────────▼───────────────────────────────┐
│ Prime Evolvable Inner Runtime                                │
│ persistent IPython state · frozen research tools · optional  │
│ specialists · evidence memory · verification · compiler      │
└──────────────────────────────┬───────────────────────────────┘
                               │ answer + full telemetry
                    ┌──────────▼──────────┐
                    │ Frozen Evaluator    │
                    └─────────────────────┘
```

For FAB, the inner loop researches, computes, verifies, and compiles an answer.
For coding domains, it changes a disposable product copy and frozen CI evaluates
the diff. The outer loop changes only declared harness surfaces. Neither Prime
session is allowed to select its own result or change the evaluator.

There is one optimizer kernel, not one optimizer per benchmark. Domains plug in
through runner and surface adapters; they do not fork the control, selection, or
evidence semantics. A future weight-training or endpoint adapter must obey the
same immutable boundary rather than introduce a second improvement loop.

## Non-negotiable loop invariants

1. Every inner rollout starts from the same immutable product seed for its case;
   product edits never become outer-loop state.
2. Every harness candidate descends from the currently selected parent; rejected
   candidates remain evidence and do not silently mutate the parent.
3. The proposer sees visible training evidence only. Adaptive-validation cases
   affect selection but not proposal content; locked-test evidence affects
   neither.
4. Evaluation code, task assignment, model/compute settings, gates, and budgets
   are outside every editable surface.
5. Promotion requires measured improvement under the frozen contract, not an
   LLM preference, narrative judgment, or proxy metric alone.
6. All outcomes—including rejection, apparatus failure, cost, and prediction
   error—are append-only evidence with a reproducible fingerprint.

## Planes

| Plane | Contents | Writable by optimizer |
| --- | --- | --- |
| Control | goal, evaluator, splits, budget, gate, permissions | no |
| Evolution | prompts, skills, tools, memory policy, workflow, middleware | yes |
| Execution | disposable product workspaces and task artifacts | per rollout only |
| Evidence | traces, metrics, diffs, decisions, fingerprints | append-only |
| Archive | candidate lineage, accepted and rejected hypotheses, anytime best | append-only |

Human governance lives above the control plane. Humans approve goals, evaluator
changes, policy exceptions, and releases; deterministic promotion remains
automatic when the frozen contract gives an unambiguous answer.

## Goal contract

Every experiment declares:

- one primary objective and its direction;
- hard constraints that cannot be traded for score;
- train, validation, and optional locked-test evidence;
- token, cost, latency, iteration, and surface-growth ceilings;
- the editable surface manifest;
- promotion and stopping policies.

The historical config name `holdout` means **adaptive validation**: its score is
used every iteration, so repeated selection can overfit it even though the
proposer cannot see its cases. `scorecard` is the locked test and is evaluated
only for the baseline and the final selected harness.

## Prime inner-loop contract

An adapter receives a task, harness variant, and immutable task state. It must:

1. create an isolated case workspace and a fresh `--no-session` Prime session;
2. invoke Prime with only the task and selected harness snapshot;
3. capture model messages, tool events, persistent computational state, evidence,
   answer or product diff, and resource use;
4. reserve a bounded no-tool compiler phase when the research phase did not
   submit, then run the evaluator outside Prime;
5. return structured outcome, resource, and behavior metrics while classifying
   apparatus failures separately;
6. discard the product workspace after preserving evidence.

Prime is the current reference runtime, not the trust boundary. Host-side process
control enforces time, turn, and cumulative-token ceilings because Prime's native
autonomous flags do not bound every tool-loop shape. Short per-phase socket paths
avoid Unix endpoint failures. This is process/workspace isolation, not a hostile
code security sandbox.

## Outer-loop contract

For each generation:

1. replay the current harness on visible training tasks;
2. normalize verifier output, bounded Prime research traces, costs, tool errors,
   and behavior telemetry, then cluster causal failure mechanisms;
3. produce diverse, bounded candidates with falsifiable predictions;
4. reject invalid or policy-breaking edits statically;
5. evaluate survivors through train then adaptive validation;
6. apply correctness, objective, cost, and integrity gates;
7. let the controller—not Prime—archive every candidate and promote at most one;
8. stop on saturation, budget exhaustion, repeated no-gain, or apparatus drift.

Rejected candidates remain evidence, not parents by default. Lessons enter
long-term memory only after replicated support; unsafe or contradictory lessons
remain quarantined.

## Evaluation hierarchy

Evidence strength increases in this order:

1. unit tests of orchestration;
2. deterministic end-to-end fixture with a real product diff and CI result;
3. objective-domain baseline with non-degenerate headroom;
4. outer-loop gain on adaptive validation;
5. locked-test gain over the seed harness;
6. equal-budget gain over retry and sequential-refinement baselines;
7. transfer to new projects or beneficiary models.

FAB v2 supplies level 3–5 evidence for a finance-research agent. It is not, by
itself, evidence that the same harness transfers to arbitrary software projects.

## Repository boundaries

```
better_harness/          optimization kernel and compatibility API
  contracts.py          immutable goal and metric definitions
  coding.py             generic coding-project inner loop
  traces.py             normalized experience evidence
  archive.py            lineage, anytime best, leaderboard
  agent.py              outer proposer adapter
  core.py               orchestration and persisted run model
  runners.py            domain adapters
benchmarks/
  agentic/               generic agent fixture
  coding/                deterministic two-loop fixture
  fabv2/                 finance-agent case study
configs/                 reproducible experiment declarations
docs/                    design, evidence, and limitations
tests/                   kernel and contract tests
```

The package keeps the `better_harness` import and CLI for compatibility with
existing artifacts. `self-harness` becomes the preferred CLI name once the
dual-loop adapter is shipped.
