# Verification standard

A green test suite proves orchestration correctness, not self-improvement efficacy.

| Level | Claim | Required evidence |
|---|---|---|
| V-1 | Experiment is ready to optimize | beneficiary stack runs; versioned data routes and evaluator are available |
| V0 | Software contract works | unit, integration, lint, artifact audit |
| V1 | Both loops are causally real | frozen CI/evaluator changes only after a harness candidate |
| V2 | Live proposer integration works | one complete atomic candidate, usage, guards, decision |
| V3 | Candidate helps the target domain | replicated matched-question gain whose family-wise interval clears the frozen floor |
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

## Measurement and promotion

Smoke runs use point estimates only and cannot support efficacy claims. A publication-grade objective
gate freezes a `[measurement]` contract before search and then:

1. compares incumbent and candidate only on identical measured question ids;
2. expresses every delta in the declared improvement direction;
3. resamples questions as clusters, retaining repeat-averaged evidence within each question;
4. adjusts the interval for `max_iterations × candidates`, the maximum pre-registered comparisons;
5. requires a complete matched matrix, enough questions, and a lower bound above the effect floor;
6. separately applies no-pass-regression, metric constraints, apparatus, cost, and latency vetoes.

The report includes an approximate minimum detectable effect (effect floor plus the simultaneous
normal critical margin). It is a planning diagnostic, not a universal sample-size law: task clusters,
provider randomness, adaptive selection, and apparatus failures still matter. When the interval is
too wide, the correct result is “unresolved under this contract,” not promotion and not proof that the
proposal was useless.

Cost is not divided into score. Quality remains primary; money, tokens, and latency are constraints
and reporting dimensions. An efficiency frontier may be reported alongside quality, but a low-cost
incomplete answer cannot outrank a correct answer merely through a favourable denominator.

An adaptive-validation winner is recorded as a provisional promotion. Only the pre-registered final
comparison and single scorecard read can support a confirmed release. The scorecard may invalidate a
generalization claim; it never sends content back into the same search run.

## Integrity rules

- Evaluator, split, model, budget, and gate fingerprints are frozen in the manifest.
- The diagnostic contract is frozen and fingerprinted; changing its layers or rules starts a new arm.
- Adaptive validation may select candidates and therefore is not called untouched.
- Scorecard content never enters proposer context and is not inspected during development.
- Apparatus failures leave both numerator and denominator; they are not task failures.
- Any cited run must pass `scripts/verify_artifacts.py`, which re-derives outcomes from raw JUnit
  evidence without using the production result parser.
- Smoke results (`n=1`, one repeat) establish lifecycle and directional evidence only.
- Independently sampled model rollouts are called matched by question, not shared-randomness paired.
- Trying more candidates than the frozen family-wise comparison count voids the confidence claim.

## Current claim ceiling

The deterministic coding fixture establishes V1. The live atomic Pi runs establish outer integration,
bounded proposal search, guards, semantic novelty checking, layer-routing hints, and correct
rejection at V2. The Public-24 run evaluated six candidates; none satisfied the frozen promotion
contract, so the strong human seed remains the best validated harness. FAB efficacy has not reached
V3.

The earlier GPT-5.6-sol + Codex 3/4 diagnostic estimated a stronger model/runtime ceiling. After a
human-directed repair sequence and frozen data fixes, the unified strong harness reached 4/4 on the
same sampled hard set; a q025 native control failed while using more tokens and time. This is not
placed on the autonomous-improvement ladder because Pi did not discover the sequence and the
Public-27 replicated arm has not run. V4 still requires a promoted harness, multiple repeats, and
equal-total-budget retry/Best-of-N under one fixed stack. See the [case study](fabv2-case-study.md)
for exact bounded results.

The q025 v5 profile is a replicated single-case success, not a V3 result: it was human-directed, the
atomic proposer did not autonomously discover the sequence, and one regression control failed while
the external price route varied. It is evidence for the layered design in ADR 0003, not for global
promotion or official leaderboard readiness.

The declarative FAB diagnostic profile is a software and search-allocation improvement at V0/V2. It
does not raise the FAB efficacy claim: no new candidate has been promoted by running this profile.
