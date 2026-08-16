# FAB v2 case study

## Question

FAB v2 is the first expensive real-domain validation of the double loop. The intended result is not
to preserve FAB's former scaffold. It is to hold the task, evaluator, model route, rollout budget,
splits, and promotion rule fixed while the outer loop searches for a finance-research harness that
makes the inner agent more correct and efficient.

This study separates two questions that are easy to conflate:

1. **Beneficiary-stack ceiling:** can a stronger model and runtime solve failures that appear stuck?
2. **Self-Harness efficacy:** with the beneficiary stack fixed, can outer search discover a harness
   that replicably beats the strong human seed and equal-budget non-evolution baselines?

Only the second question is evidence of harness self-improvement.

## Public-24 evolution result

`runs/fabv2-public24-context-v2` is a pre-registered 8 train / 8 adaptive-validation / 8 locked-
scorecard run with DeepSeek V4 Flash, Prime, one repeat, two candidates per iteration, and three
iterations. The primary metric was ungated numeric credit; promotion required at least +0.03 on both
development splits and no pass-count regression.

The strong seed scored:

| Split | Passes | Mean ungated credit |
|---|---:|---:|
| Train | 0/8 | 0.1583 |
| Adaptive validation | 2/8 | 0.2375 |
| Locked scorecard | 1/8 | 0.1458 |

All six proposals were rejected. Two improved both continuous development metrics but missed a
pre-registered constraint: iteration 1 candidate 1 reached +0.1500 train and +0.0281 validation,
just below the +0.03 floor; iteration 2 candidate 1 reached +0.0667 and +0.0646 but regressed
validation passes from 2/8 to 1/8. Two candidates overfit with negative validation deltas. One failed
the effect floor and pass constraint. The final proposal was semantically identical to an earlier
JSON policy and is now rejected before rollout rather than receiving an unregistered retry.

The final harness is therefore byte-for-byte the strong human seed. Outer search consumed 187,041
tokens. The independent artifact audit re-derived 13/13 recorded passes over 104 case rollouts with
zero missing XML outcomes. Because this is one repeat and no candidate was promoted, it establishes
correct search and conservative rejection—not automatic improvement.

## GPT-5.6-sol + Codex ceiling diagnostic

The user's proposed control was run on four tasks that the same strong harness failed under
DeepSeek+Prime. `runs/fabv2-codex-gpt56sol-upper-bound-v2` used local Codex CLI 0.147.0,
`gpt-5.6-sol`, medium reasoning effort, the same strong harness, the same `fab_tools.py`, and the same
frozen numeric judge. The agent could not inspect rubrics or evaluator code. The requested model is
documented in the [official OpenAI model guide](https://learn.chatgpt.com/docs/models).

| Task | Pass | Partial / ungated credit | Wall time |
|---|---:|---:|---:|
| q004 | yes | 1.0000 | 104.5 s |
| q013 | yes | 0.8000 | 276.2 s |
| q022 | yes | 0.9000 | 180.3 s |
| q025 | no | 0.4667 | 354.9 s |
| **Mean** | **3/4** | **0.7917** | — |

This is a **model+runtime upper-bound diagnostic**, not a pure model ablation: both DeepSeek→GPT and
Prime→Codex changed. It nevertheless gives strong causal guidance. Many apparent “needs more harness
iterations” failures are within reach of a stronger beneficiary stack; they are not evidence that
the outer method must keep rewriting prompts. But the result does not exonerate the method entirely.
On q025, Codex used FY2027 guidance ratios as the forecast baseline instead of the requested FY2026
actuals, missing seven FY2026 inputs and adjusted EBITDA. That is a definition/base-period reasoning
failure, not an empty submission or simple budget truncation. The present outer diagnosis collapses
too many numeric failures into `no_verification_before_submit`, so it is not yet precise enough to
target this class reliably.

An earlier `v1` diagnostic is invalid apparatus evidence: its usage-ledger path was outside Codex's
writable sandbox. It is retained locally only to preserve the failure history and is not included in
the result.

## What is and is not established

- The controller, frozen boundary, atomic proposer, guards, resume logic, scorecard isolation,
  artifact audit, and semantic novelty guard work.
- The current bottleneck is mixed: the DeepSeek+Prime beneficiary stack is a major limitation, while
  coarse failure diagnosis and weak proposal search are method limitations.
- No evolved harness has yet beaten the strong seed under the Public-24 contract. FAB efficacy has
  not reached V3.
- The project cannot claim a global optimum, stable recursive compounding, or leaderboard readiness.
  Public questions and numeric rubrics are an unofficial diagnostic; the official Vals leaderboard
  is private and uses its own submission path.
- A strict model-only ablation still requires GPT-5.6-sol inside Prime with identical runtime,
  prompts, tools, and budgets. Local Codex subscription authentication is not presently a Prime
  provider route, so that comparison has not been run.

The strongest honest conclusion is: **a stronger model/runtime directly solves most of the sampled
stuck cases, while the current Self-Harness implementation correctly rejects weak edits but has not
yet demonstrated a stable improvement over its strong human seed.**
