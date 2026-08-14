# Benchmarks

Benchmarks own task data, immutable product seeds, frozen evaluators, and the
initial harness implementation. Optimizer-writable surfaces are declared in a
config; everything else belongs to the control or execution plane.

- `coding/`: tiny deterministic fixture proving that an outer harness edit can
  cause an inner coding agent to repair a disposable product while the seed and
  CI remain unchanged.
- `agentic/`: deterministic agent-harness tasks used by earlier experiment
  stages and regression tests.
- `fabv2/`: finance-research case study with a frozen numeric rubric evaluator.

During evaluation, source harness directories are never patched. Every variant
receives a private snapshot under its run artifacts, which permits concurrent
experiments without cross-contamination.
