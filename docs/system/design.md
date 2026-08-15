# Design: controller authority, Prime agency

## Framework decision

Prime Agent is the reference execution runtime because its persistent IPython
kernel, file workspace, extensible tools, and subagent model fit long-horizon
research and coding tasks. It is used in two causally separate roles:

- inner runtime: solve one task under one harness snapshot;
- outer proposer: diagnose visible failures and edit declared harness surfaces.

Prime does not own experiment state, evaluation, or selection. The Python
controller freezes those functions and can reject every Prime proposal. The
legacy DeepAgents proposer remains a compatibility adapter for non-FAB fixtures;
FAB has no model-library or official-harness execution path.

## Frozen and evolvable planes

| Frozen controller plane | Evolvable harness plane |
| --- | --- |
| goal and primary metric | system policy |
| task assignment and split membership | orchestration and stopping policy |
| beneficiary/proposer model endpoints | tool-use guidance |
| evaluator and research-tool implementation | research strategy |
| turn, token, time, cost, and growth limits | evidence memory policy |
| promotion gate and scorecard access | specialist delegation policy |
| immutable rollout artifacts | verification and answer compilation |

The outer proposer receives train failures, normalized bounded traces, verifier
feedback, current surfaces, and prior visible decisions. It never receives
adaptive-validation or scorecard cases. Shared parametrized test sources are
withheld rather than heuristically redacted.

## Inner runtime

Each FAB rollout creates a private case workspace and copies only the selected
eight surfaces plus frozen tool/provider adapters. Research runs in a fresh Prime
`--no-session` process with persistent computational state inside the case. The
host streams JSON events and stops the process at the declared cumulative token,
assistant-turn, or time boundary.

The runtime is explicitly two-phase:

1. bounded research acquires facts, computes results, and maintains evidence;
2. a reserved no-tool compiler converts structured evidence and a bounded trace
   into the final answer when research has not already submitted.

The compiler is an architectural stage, not a score-specific recovery prompt.
Non-empty streamed compiler output remains a valid submission even when the host
stops the process immediately afterward at the hard token boundary. All phase
usage is combined for cost and latency gates.

## Outer proposal and promotion

For each iteration the controller:

1. evaluates the current parent on visible train cases;
2. normalizes failure assertions, judge feedback, tool counts/errors, stop reason,
   token use, and a bounded tail of the Prime research trace;
3. asks one or more isolated Prime proposer sessions for small, falsifiable edits;
4. rejects leaks, forbidden edits, syntax errors, or excessive growth statically;
5. evaluates survivors on train and then adaptive validation;
6. vetoes pass regressions and excessive token/cost/latency growth;
7. promotes at most one best survivor and archives all decisions.

Every proposal records root cause, evidence, expected pass flips, and at-risk
cases. Prediction accuracy is evidence about whether the loop understands its
changes; it is not itself the correctness metric.

## FAB protocol

Public-27 is a community development study, not the official blind leaderboard.
The active full contract assigns eight cases each to train, adaptive validation,
and locked scorecard, leaving three public questions outside Numeric-24. Search
uses one repeat for cost control; any selected result must be confirmed with
multiple repeats under a new frozen confirmation contract.

Required arms are:

1. minimal Prime harness, zero evolution;
2. strong human seed, zero evolution;
3. evolved harness selected by the controller;
4. equal-token retry/Best-of-N or sequential refinement;
5. locked scorecard once for the preregistered final comparison.

“Best” means the highest validated candidate found within this declared search
space and budget. A global optimum, official FAB rank, stable compounding, or
cross-project transfer requires separate evidence.

## Known limits

- Prime workspaces are not a complete security sandbox.
- Public rubrics reduce blindness even when the proposer cannot access them.
- Adaptive validation can be overfit through repeated selection.
- One-repeat search is noisy and only suitable for candidate discovery.
- Frozen-weight harness evolution changes behavior distributions but is not, by
  itself, evidence of recursive weight-level self-improvement.
