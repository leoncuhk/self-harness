# FAB v2 bounded case study

> Historical record: the tables below were produced by the removed
> official/model-library-based FAB apparatus. They are retained only as negative
> evidence and are not executable baselines for the Prime architecture.

The active study now uses:

- `fabv2_prime_smoke.toml` for a three-case lifecycle and headroom check;
- `fabv2_prime_minimal.toml` for a contract-matched minimal-harness arm;
- `fabv2_prime.toml` for the Public-27 8/8/8 train/adaptive-validation/locked-
  scorecard protocol;
- Prime Agent for both the inner runtime and outer proposer;
- eight evolvable surfaces and a frozen evaluator-owned research tool substrate.

No Prime efficacy result is claimed here until minimal, strong, evolved, and
equal-budget comparator arms have completed under the same frozen contract.

All arms use the same model, one case per split, and the same eight-turn, 360-second, 5,000-output-token-per-call limits.

| Arm | Train score (pass) | Validation score (pass) | Locked-test score (pass) | Final-arm eval tokens | Optimization rollout tokens | Outer-search tokens | Wall time | Changed surfaces |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Seed | 0.000 (0/1) | 0.000 (0/1) | 0.000 (0/1) | 147,205 | 0 | 0 | 662.0s | none |
| Hand-engineered B5 | 0.000 (0/1) | 0.000 (0/1) | 0.000 (0/1) | 169,058 | 0 | 0 | 673.3s | none |
| Self-Harness final | 0.000 (0/1) | 0.000 (0/1) | 0.000 (0/1) | 147,205 | 143,581 | 1,112,474 | 662.0s | none |

Optimization rollout tokens are the rejected candidate's train and validation evaluations, separate from final-arm measurement. Outer-search tokens are provider reported and include cache-read tokens; the proxy did not report currency cost. B5 is a predefined baseline, so `none` means no within-arm evolution rather than the seed prompt.

Legacy `numeric_recall` below is rubric numeric coverage, not answer recall:

| Arm | Train | Validation | Locked test |
| --- | ---: | ---: | ---: |
| Seed | 0.750 | 1.000 | 1.000 |
| Hand-engineered B5 | 0.750 | 1.000 | 1.000 |
| Self-Harness final | 0.750 | 1.000 | 1.000 |

This legacy metric is answer-independent for a fixed question and must not be interpreted as finding 75% or 100% of requested values. The executed v1 objective also collapses any failed dealbreaker to zero, producing a discontinuous all-zero search landscape. `configs/fabv2_self_harness_v2.toml` pre-registers an ungated severity-weighted optimization signal while retaining the official dealbreaker score and binary pass result for reporting; v2 has not been executed.

## Outer-loop outcome

Candidate `iter-001` was rejected; train 0.000 (0/1), validation 0.000 (0/1).

Gate: objective gate (score, maximize): Δ_in=+0.0000 Δ_ho=+0.0000; constraint, regression, or effect floor failed

Predicted flips: tests/test_fabv2.py::test_question[q004].

## Interpretation boundary

Validation score delta (final - seed): +0.000.
Locked-test score delta (final - seed): +0.000.

This is a causal integration check with n=1 per split and one stochastic repeat. It cannot establish a competition-wide ranking, statistical significance, transfer, or a global optimum. A promoted candidate establishes only the best validated harness found in this frozen run budget.

The later continuous-objective calibration is recorded separately in
[`fabv2-v2-calibration.md`](fabv2-v2-calibration.md); it also produced no gain
and identified eight-turn budget exhaustion plus resume/instrumentation defects.
