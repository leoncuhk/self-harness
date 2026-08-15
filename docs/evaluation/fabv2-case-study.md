# FAB v2 case study

## Purpose

FAB v2 is the first expensive real-domain validation of the general double loop. The target is not to
reuse FAB's former harness; it is to let a fixed model plus Prime inner runtime automatically acquire
a more reliable and efficient finance-research harness through execution, diagnosis, modification,
validation, and selection.

The active contracts are:

- `configs/fabv2_smoke.toml`: Prime inner lifecycle, no evolution;
- `configs/fabv2_evolve_smoke.toml`: one-case train/validation/scorecard mechanism check;
- `configs/fabv2_minimal.toml`: contract-matched minimal comparator;
- `configs/fabv2.toml`: Public-27 Numeric-24 8/8/8 development protocol.

## Measured status

Corrected strong-harness smoke evidence with DeepSeek V4 Flash is mixed: q004 passed; q005 failed
after finding 4/8 numeric obligations and exhausting 142,159 tokens; q006 remained below its pass
threshold. These are single stochastic runs, not population estimates.

Two open-ended Prime outer attempts used roughly 120k–140k tokens each and produced no candidate. A
tool-using Pi attempt identified the correct long-document failure and edited surfaces, but reached
132,004 tokens before writing the required proposal. Both were correctly rejected before evaluation.

The atomic Pi protocol then produced a complete two-surface candidate in one call (17,224 tokens,
58.7 seconds). It attributed q005 to repeated large search windows, 12 `search-page` calls, 14 IPython
calls, zero calculator calls, and loss of the computation/submission reserve. This proves proposer
integration and a trace-grounded candidate, not candidate efficacy. Its Controller-gated smoke result
must be recorded here before any stronger claim.

## Claim boundary

Public FAB questions and rubrics support an unofficial reproducible community evaluation, not the
official private leaderboard. A one-case smoke can reject a broken integration or reveal a causal
mechanism; it cannot establish statistical significance, equal-budget superiority, transfer, stable
compounding, or a global optimum. The strongest permitted phrase is “best validated candidate found
under the named frozen contract and budget.”
