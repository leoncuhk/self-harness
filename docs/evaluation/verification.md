# Verification standard

A green test suite proves orchestration correctness, not self-improvement efficacy.

| Level | Claim | Required evidence |
|---|---|---|
| V-1 | Experiment is ready to optimize | beneficiary stack runs; versioned data routes and evaluator are available |
| V0 | Software contract works | unit, integration, lint, artifact audit |
| V1 | Both loops are causally real | frozen CI/evaluator changes only after a harness candidate |
| V2 | Live proposer integration works | one complete atomic candidate, usage, guards, decision |
| V3 | Candidate helps the target domain | replicated train and adaptive-validation gain |
| V4 | Search method adds value | beats strong zero-evolution and equal-total-budget retry/Best-of-N |
| V5 | Result generalizes | one-shot scorecard plus new tasks, projects, or models |
| V6 | Recursive compounding | later generations improve the ability to generate further gains |

## FAB protocol

The main contract uses Public-27 as an unofficial community study. It assigns 8 train, 8 adaptive
validation, and 8 locked scorecard questions; the remaining public questions are excluded by the
Numeric-24 rule. Public rubrics mean this cannot be represented as an official blind FAB score.

Required arms under identical model, task, and per-rollout budgets:

1. minimal harness, zero evolution;
2. strong human seed, zero evolution;
3. evolved harness;
4. retry or Best-of-N using the same total optimization tokens;
5. multiple repeats for the final comparison;
6. one scorecard read after selection is complete.

Before these arms, run a readiness diagnostic. A weak beneficiary-stack ceiling or unavailable,
mutable source route is an experiment-contract problem, not evidence for another harness mutation.
External financial inputs used for promotion should be served from a versioned snapshot or host
service with recorded hashes. If that condition changes, results belong to different arms.

Report objective, gated pass rate, per-case deltas, tokens, latency, apparatus failures, prediction
precision, and the full candidate ledger. Do not add gains from experiments with different baselines.

## Integrity rules

- Evaluator, split, model, budget, and gate fingerprints are frozen in the manifest.
- Adaptive validation may select candidates and therefore is not called untouched.
- Scorecard content never enters proposer context and is not inspected during development.
- Apparatus failures leave both numerator and denominator; they are not task failures.
- Any cited run must pass `scripts/verify_artifacts.py`, which re-derives outcomes from raw JUnit
  evidence without using the production result parser.
- Smoke results (`n=1`, one repeat) establish lifecycle and directional evidence only.

## Current claim ceiling

The deterministic coding fixture establishes V1. The live atomic Pi runs establish outer integration,
bounded proposal search, guards, semantic novelty checking, layer-routing hints, and correct
rejection at V2. The Public-24 run evaluated six candidates; none satisfied the frozen promotion
contract, so the strong human seed remains the best validated harness. FAB efficacy has not reached
V3.

The separate GPT-5.6-sol + Codex 3/4 diagnostic estimates a stronger model/runtime ceiling. It is not
placed on this ladder because it changes the beneficiary stack and performs no harness evolution.
V4 still requires a promoted harness, multiple repeats, and equal-total-budget retry/Best-of-N under
one fixed stack. See the [case study](fabv2-case-study.md) for exact bounded results.

The q025 v5 profile is a replicated single-case success, not a V3 result: it was human-directed, the
atomic proposer did not autonomously discover the sequence, and one regression control failed while
the external price route varied. It is evidence for the layered design in ADR 0003, not for global
promotion or official leaderboard readiness.
