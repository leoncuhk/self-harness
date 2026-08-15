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
                    │ Atomic Pi Proposer │
                    │ one call, no tools │
                    │ JSON patch + claim │
                    └──────────┬──────────┘
                               │ validated declared surfaces
┌──────────────────────────────▼────────────────────────────────┐
│ Evolvable Prime Inner Runtime                                 │
│ orchestrator · persistent computation · research/data tools   │
│ specialist RLMs · evidence memory · verification · compiler   │
└──────────────────────────────┬────────────────────────────────┘
                               │ answer/product diff + telemetry
                    ┌──────────▼──────────┐
                    │ Frozen Evaluator   │
                    └────────────────────┘
```

Only the Controller promotes a candidate. Neither Prime nor Pi can change the goal, task assignment,
evaluator, model route, inference budget, resource gate, scorecard, or historical archive.

## Inner loop

Each rollout starts from a private harness snapshot and fresh `--no-session` agent process. FAB uses
Prime because the task benefits from persistent IPython state and optional `rlm(...)` specialists.
The host enforces time/token/turn ceilings, attributes child usage, persists full telemetry, and
reserves a separate no-tool compiler so a research cutoff does not force an empty answer.

For coding projects, the runner creates a disposable product checkout, lets the inner agent modify
only product files, and runs CI outside the agent. Product changes never mutate the harness source.

## Outer loop

The Controller normalizes visible failing traces, clusters failure mechanisms, and builds one bounded
context containing only task instructions, normalized experience, failure clusters, and current
surfaces. Pi receives that context with all tools disabled and returns one JSON object containing:

- a root-cause claim and evidence;
- predicted pass flips and regression risk;
- complete replacement text for declared changed surfaces.

Parsing and application are atomic. Invalid JSON, partial output, empty surface text, or undeclared
surface names cause rejection before any rollout. This task is a constrained transformation, so an
open-ended coding-agent file loop adds cost and failure modes without useful capability.

## Selection

A candidate must pass static path/leak/syntax/growth guards, improve the primary train objective by
the frozen floor, avoid pass and constraint regressions, remain inside cost/latency ceilings, and
satisfy the same rule on adaptive validation. At most one candidate is promoted per generation.

The scorecard is unavailable to the proposer and does not participate in selection. Because
validation is consulted repeatedly, it is called adaptive validation rather than an untouched
holdout. Every decision, rejected candidate, prediction, resource measurement, and lineage edge is
retained for replay.

## Security and causality

Private workspaces and allowlisted surfaces protect attribution, not host security. A production
deployment must additionally use a container/VM sandbox, least-privilege secrets, egress policy, and
an evaluator service the agent process cannot modify.
