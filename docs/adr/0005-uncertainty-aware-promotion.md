# ADR 0005: Uncertainty-aware promotion

Status: accepted

## Context

Repeated evaluation previously produced an aggregate pass rate and mean objective. That reduces
noise but does not quantify whether a candidate is distinguishable from its incumbent. Repeatedly
selecting the best of several candidates also creates an optional-stopping and multiple-comparison
path to false promotion. A fixed `min_delta` alone cannot close either path.

Simple `score/token` optimization is not a solution. It changes the target, becomes unstable at small
denominators, and can reward early exit or incomplete answers. Cost should constrain a quality
improvement, not redefine correctness.

## Decision

Publication-grade objective gates may enable a frozen `MeasurementContract`. The Controller matches
incumbent and candidate outcomes by question id, converts differences into the configured improvement
direction, and uses question-cluster bootstrap intervals. The per-comparison error rate is Bonferroni
adjusted against the pre-registered maximum `max_iterations × candidates`.

Promotion requires:

- at least `minimum_pairs` measured questions;
- simultaneous lower bounds showing neither train nor adaptive validation regressed;
- the required split's lower bound above `goal.min_delta`;
- the existing pass-regression, metric, apparatus, cost, latency, and edit guards.

The estimate records matched pair count, missing questions, mean delta, interval, family-wise
comparison count, and approximate minimum detectable effect. Bootstrap randomness is seeded and the
measurement contract is written to the manifest and evaluation fingerprint.

The term “matched” is intentional. Questions are paired, but model randomness is not necessarily
shared. A provider seed may be recorded when available; the Controller does not claim deterministic
pairing that the runtime cannot enforce.

Adaptive-validation winners are provisional promotions. A confirmed release requires the separate,
pre-registered replicated confirmation and locked scorecard protocol.

## Consequences

- Real but small gains may be rejected when the experiment lacks resolution. This is preferable to
  promoting noise.
- More candidate search makes each interval stricter unless the family is separately pre-registered.
- Question heterogeneity becomes visible instead of being hidden inside one aggregate score.
- The bootstrap does not solve benchmark leakage, judge validity, temporal data drift, or proposer
  weakness; those remain separate experimental risks.
- Smoke and deterministic coding contracts can leave measurement disabled. The replicated FAB
  evolution contract enables it.
