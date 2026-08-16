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

### Direct native-Codex control on q025

`runs/fabv2-codex-native-q025-v1` removed the project strong harness and gave a fresh, rubric-blind
Codex process only q025, the public tools, and the output contract. This one pre-registered attempt
also failed: 0.000 gated credit, 0.400 ungated credit, 0.4615 numeric recall, 335.3 seconds, and a
normal process exit. It estimated $237.96 billion instead of approximately $239.207 billion.

The native and strong-harness Codex attempts independently made the same substantive choice: they
used FY2027 guidance percentages to construct operating margin, D&A, restructuring, SBC, and CapEx,
rather than carrying forward the requested FY2026 actual base. Removing Prime and removing the
project harness therefore do not solve q025. This is evidence of a stable task-interpretation error
under the sampled GPT-5.6-sol stack.

### q025 diagnostic micro-evolution

A human-directed, Codex-assisted frozen sequence then tested whether general harness construction could repair q025 without
encoding Salesforce, FY2026, q025, or target numbers. Each revision addressed the newly observed
failure mechanism; semantically identical retries were not used.

| Arm | New general mechanism | Gated / ungated | Result |
|---|---|---:|---|
| Native Codex | no project harness | 0.000 / 0.400 | wrong guidance-period ratios |
| Strong harness | existing project seed | 0.467 / 0.467 | wrong guidance-period ratios |
| v1 | forecast source-period provenance | 0.000 / 0.333 | chose actuals but invented missing inputs |
| v2 | resolve 8-K exhibits through filing index | 0.000 / 0.333 | used unavailable HTML index, fell back to FY2025 |
| v3 | deterministic `<accession>/index.json` route | 0.733 / 0.733 | exact EV; three subtotals not materialized |
| v4 | explicit derived subtotal/sign compiler | 0.000 / 0.600 | incorrectly deducted SBC a second time |
| **v5** | FCFF noncash reconciliation invariant | **1.000 / 1.000** | **13/13 criteria, both MUST criteria passed** |

The frozen v5 profile then passed q025 in two additional independent repeats: **3/3 passes, all at
1.000**, with wall times of 251.9, 295.9, and 273.4 seconds. This is strong evidence that harness
construction fixed the known training case, not merely a lucky single rollout. The reusable changes
span four surfaces: forecast provenance in orchestration, SEC exhibit discovery in tools, noncash
FCFF reconciliation in verification, and explicit subtotal/sign materialization in submission.

The negative control is equally important. On three tasks previously passed by the strong harness,
v5 scored q004=1.000, q013=0.600 (failed), and q022=0.900. q013's `price-history` calls were blocked
inside the isolated workspace and the fallback source returned a different unaffected price; the new
forecast rules were not active on that task. This looks more like data-route variance than a direct
policy conflict, but the frozen no-regression gate cannot waive it after seeing the result.

Therefore v5 is archived at
`benchmarks/fabv2/harnesses/experimental/forecast-provenance-v1` as a successful q025 case study,
but it is **not promoted** over `harnesses/strong`. A global promotion requires replicated controls
with a frozen data plane and non-degrading adaptive validation. This sequence demonstrates what a
good outer loop must discover, but it is not evidence that the current atomic Pi proposer discovered
the chain autonomously.

## Unified hard-case regression and native control

The q013 regression was then decomposed rather than waived. Chart's definitive merger proxy reports
the July 28, 2025 close as $171.65, and its FY2024 10-K reports revenue of $4,160.3 million, SG&A of
$547.4 million, and amortization separately at $193.9 million. The failed run had both a broken
historical price route and a fabricated $638.9 million “filed SG&A” claim. Prompt rules alone did not
repair this: after the price snapshot was added, q013 still scored only 0.600 because the live SEC
ticker map no longer contained delisted GTLS.

The evaluator data plane now supports bounded historical ticker-to-CIK indexes, official market
observations, and checksummed verbatim SEC excerpts. With those routes plus the general q025
forecast/FCFF and exact-line-item rules in the unified strong harness, a fresh rubric-blind
GPT-5.6-sol + Codex regression produced:

| Task | Gated / ungated | Wall time |
|---|---:|---:|
| q004 | 1.000 / 1.000 | 122.9 s |
| q013 | 1.000 / 1.000 | 250.6 s |
| q022 | 1.000 / 1.000 | 243.3 s |
| q025 | 1.000 / 1.000 | 278.0 s |
| **Mean** | **1.000 / 1.000** | — |

q013 also passed an immediately preceding fresh run at 1.000. For attribution, a new q025 native
Codex control retained the same model, deterministic tools, frozen data, timeout, and numeric judge
but removed the project harness. It failed at 0.000 gated / 0.600 ungated, used 1,192,962 input
tokens, and took 395.8 seconds. The unified strong arm used 653,863 input tokens and 278.0 seconds.
Thus model capability and repaired data access were necessary but not sufficient on q025; the
harness changed both correctness and efficiency in this sampled comparison.

This is still targeted development evidence. The four cases were selected because they had failed,
the final chain was human-directed, and only one unified four-case repeat has been run. It supports
“the known hard cases are currently solved,” not “the autonomous outer loop improved itself,” “the
Public-27 optimum was reached,” or “the system can enter the official leaderboard.”

## What is and is not established

- The controller, frozen boundary, atomic proposer, guards, resume logic, scorecard isolation,
  artifact audit, and semantic novelty guard work.
- The current bottleneck is mixed: the DeepSeek+Prime beneficiary stack is a major limitation, while
  coarse failure diagnosis and weak proposal search are method limitations.
- No autonomously evolved harness has yet beaten the strong seed under the Public-24 contract. The
  later 4/4 result is a human-directed unified hard-case repair, not a Pi promotion.
- The project cannot claim a global optimum, stable recursive compounding, or leaderboard readiness.
  Public questions and numeric rubrics are an unofficial diagnostic; the official Vals leaderboard
  is private and uses its own submission path.
- A strict model-only ablation still requires GPT-5.6-sol inside Prime with identical runtime,
  prompts, tools, and budgets. Local Codex subscription authentication is not presently a Prime
  provider route, so that comparison has not been run.

The strongest honest conclusion is: **the unified system now solves all four sampled hard cases and
the q025 native control shows independent harness value, while autonomous outer search has not yet
demonstrated a stable improvement over its strong human seed or leaderboard readiness.**
