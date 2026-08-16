# ADR 0004: Keep domain diagnosis declarative and outside the core

- Status: accepted
- Date: 2026-08-16

## Decision

The framework core owns only generic operational evidence, immutable experiment contracts, candidate
execution, and promotion. Each vertical benchmark owns a frozen declarative diagnostic contract
containing:

- a controlled failure-layer vocabulary;
- short proposer guidance about editable and non-editable layers;
- deterministic named facets expressed as regular-expression rules and match thresholds.

The contract is loaded from TOML, serialized into the run manifest and evaluation fingerprint, and
rendered into the bounded proposer context. It is data, not executable plugin code. The generic
contract contains no finance vocabulary; FAB owns its finance profile under
`benchmarks/fabv2/contracts/diagnostics.toml`.

## Why

The first FAB implementation placed forecast-period, SEC-exhibit, FCFF, and answer-materialization
rules directly in the generic trace normalizer and named finance layers in Pi's global system prompt.
That improved one benchmark but silently made every future coding or scientific experiment reason in
FAB categories. It also made changing a diagnostic rule invisible to the experiment fingerprint.

An unrestricted Python plugin would separate files but enlarge the trusted execution surface. A
small declarative contract is sufficient for reproducible routing hints. It deliberately does not
claim to infer root cause: the outer proposer still has to make a falsifiable causal hypothesis, and
the frozen evaluator still decides whether the resulting candidate helped.

## Consequences

- Adding a vertical requires no change to `traces.py`, `pi.py`, the gate, or the Controller.
- Changing layers or facet rules changes the evaluation fingerprint and therefore starts a different
  experimental contract.
- Generic operational facets such as budget boundary, data-plane access, and a numeric verifier miss
  remain in the core. Runtime-specific observations such as a missing submission are emitted by the
  runtime adapter through the same validated facet vocabulary; the core does not infer Agent tool
  semantics.
- Declarative pattern matching is intentionally bounded. If a domain needs richer typed diagnosis,
  its runner should emit structured telemetry; it should not grow an opaque regex language or give
  the proposer private evaluator access.
- A diagnostic contract improves search allocation, not task capability. It cannot compensate for a
  weak beneficiary model, an unfrozen data plane, or an invalid evaluator.
