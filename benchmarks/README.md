# Benchmarks

- `coding/` is a deterministic proof that an outer harness edit can cause an inner coding agent to
  repair a disposable product while product seed and CI remain frozen.
- `fabv2/` is the real finance-research case study: Public-27 data, Prime runtime, initial harnesses,
  evaluator-owned tools, and frozen numeric evaluator.

Source harnesses are never patched during evaluation. Every variant receives a private run-local
snapshot, so concurrent candidates remain attributable and replayable.
