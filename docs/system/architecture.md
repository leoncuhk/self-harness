# Architecture: two loops, one immutable anchor

## System claim

This project optimizes a coding-agent harness. It does not claim to find a
global optimum. A run produces the best validated harness found under a frozen
goal contract and a recorded resource budget.

The two loops are deliberately separate:

```
inner loop: task -> coding agent -> product diff -> CI/verifier -> outcome/trace
outer loop: traces -> diagnosis -> harness candidates -> inner-loop replay -> promotion
```

The inner loop changes a disposable copy of a product. The outer loop changes
the prompt, skills, tools, memory policy, workflow, and middleware used by the
coding agent. Neither loop may change the goal contract, evaluator, private
cases, resource ceiling, promotion rule, or audit log.

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

## Inner-loop contract

A coding-project adapter receives a task, a harness variant, and an immutable
product seed. It must:

1. create an isolated worktree or copy;
2. invoke the configured coding agent with only visible task material;
3. capture the agent transcript and product diff;
4. run the frozen CI commands outside the agent process;
5. return structured metrics and apparatus failures separately;
6. discard the product workspace after preserving evidence.

The adapter is command based so Codex, Claude Code, OpenCode, or a deterministic
test double can implement the same protocol.

## Outer-loop contract

For each generation:

1. replay the current harness on visible training tasks;
2. normalize traces and cluster causal failure mechanisms;
3. produce diverse, bounded candidates with falsifiable predictions;
4. reject invalid or policy-breaking edits statically;
5. evaluate survivors through train then adaptive validation;
6. apply correctness, objective, cost, and integrity gates;
7. archive every candidate and promote at most one;
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
