# FAB v2 V4 execution audit

Audit date: 2026-08-15. This note re-derives claims from raw `judge.json`,
`run.json`, JUnit, decisions, and the prediction ledger. It supersedes informal
run summaries; it does not alter historical artifacts.

## Verdict

V4 is a meaningful engineering advance and the first **exploratory positive**
for the real FAB development loop. It is not yet confirmed efficacy, stable
compounding, generalization, or a best-known FAB harness.

The causal chain now works once: inner-loop behavior telemetry exposed turn
exhaustion, missing calculator use, and missing submission; the outer proposer
edited four policy surfaces; the next q004 rollout used the calculator, submitted
within the main phase, and raised the local continuous diagnostic from 0 to
0.285714. The gate accepted that candidate. This is stronger evidence than a
fixture and stronger than merely rejecting bad edits.

The evidence remains weak because it is one stochastic rollout on one exposed
training question. Iterations 2 and 3 added no accepted gain, all three predicted
binary pass flips missed, and the sole holdout stayed at zero throughout.

## Independently reproduced arm comparison

`scripts/audit_fabv2_judges.py` recomputes these values directly from six unique
baseline `judge.json` files per arm:

| Aggregate | B0u official prompt | B5u V2 prompt | Delta |
| --- | ---: | ---: | ---: |
| Question-mean ungated credit | 0.348545 | 0.554563 | +20.60 pp |
| Global severity-weighted credit | 0.333333 | 0.520833 | +18.75 pp |
| Question-mean gated partial | 0.214286 | 0.333333 | +11.90 pp |
| Non-empty answers | 6/6 | 6/6 | 0 |

B5u was non-inferior question by question: four improved and two tied. This is
a useful directional hand-engineered-harness result at six questions × one
repeat. The previously reported 0.386 and 0.590 aggregates cannot be reproduced
from the persisted judge artifacts under either the question mean or the global
severity-weighted definition and must not be cited.

Both `u` arms changed the compute contract by adding a recovery phase after the
14-turn main phase. They are comparable to each other, but not equal-budget
comparators for the original B0/B5 arms. The historical runner omitted recovery
tokens, turns, errors, and tool calls from `run.json`; wall-clock duration did
include recovery. Therefore historical exact token ratios are incomplete.

## V4 evolution result

| Iteration | Train ungated delta | Holdout delta | Decision | Predicted binary flip |
| --- | ---: | ---: | --- | --- |
| 1 | +0.285714 | +0.000000 | accepted | missed |
| 2 | -0.285714 | +0.000000 | rejected | missed |
| 3 | +0.000000 | +0.000000 | rejected | missed |

The final selected artifact is iteration 1. The report's `0/1` train row is the
binary pass score, while the promotion objective was `ungated_credit`; those are
different measures, not a contradiction. No separate repeated confirmation of
the selected artifact was performed. The ledger records one acceptance in three
iterations, prediction precision 0/3, and no observed pass/fail flips.

The scorecard is no longer sealed in the current artifacts. Its single q019
rollout moved from ungated 0.75 to 0.833333 but remained gated partial 0. One
public, previously exposed question at one repeat is not confirmatory evidence.

All 16 persisted V4 JUnit outcomes and all 12 B0u/B5u outcomes agree with the
recorded result statuses under `scripts/verify_artifacts.py`.

## Evidence defects found and corrected prospectively

The audit found three contract defects in the executed V4 run:

1. Recovery accounting omitted recovery tokens, turns, errors, and tool usage,
   and returned the original stop reason even after a recovery submission.
2. Budget-message and recovery switches lived in `.env`, outside the runner
   config, evaluation fingerprint, manifest, and command record. A resume could
   therefore treat behaviorally different evaluations as reusable.
3. V4 described a “single recovery turn,” but allowed up to three turns and 120
   seconds. A recovery trace in iteration 3 used two turns after first requesting
   a disabled calculator.

The implementation now merges phase accounting, emits explicit recovery
telemetry and stop reasons, and passes all recovery settings through
`runner.pytest.env`. Runner config and its fingerprint are persisted in the run
manifest. These fixes apply to future measurements; they do not retroactively
repair V4 costs. The V4 config was not committed before outcomes, so its
“pre-registration” is a declared execution intention rather than an immutable,
Git-timestamped preregistration.

## Scientific boundary and next gate

Public rubric failures expose exact expected values to the proposer. That is
legitimate adaptive development on Public-27, but it is answer-aware optimization,
not blind transfer. The proposer explicitly cited expected q004 values, then
adapted repeatedly to that one question.

The next efficacy gate should freeze the accepted harness and run:

1. at least three repeats on a multi-question train/holdout split;
2. a total-compute-matched retry or best-of-N comparator;
3. complete recovery accounting under the fingerprinted runner contract;
4. a still-sealed scorecard used once after selection.

Until that passes, the correct status is: **mechanism complete; one real
exploratory improvement observed; efficacy not confirmed**.
