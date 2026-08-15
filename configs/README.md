# Experiment configurations

Each TOML file is an executable experiment contract, not merely runtime
configuration. It fixes the target workspace, model, editable surfaces, data
splits, proposer budget, evaluation budget, gate, and resource ceilings.

- `coding_demo.toml`: deterministic product-development dual-loop fixture.
- `fabv2_self_harness.toml`: bounded FAB v2 structural self-harness study.
- `fabv2_self_harness_v2.toml`: pre-registered successor with an ungated
  severity-weighted search objective; its executed eight-turn calibration
  produced only empty submissions and no objective gain.
- `fabv2_self_harness_v3.toml`: unexecuted 14-turn successor, versioned rather
  than silently changing V2 after observing its budget-exhaustion result.
- `fabv2_public27_self_harness.toml`: expensive 18/9 Public-27 adaptive
  development run with three repeats and two candidates; it has not been
  executed and its holdout is explicitly not a locked test.
- `fabv2_public27_b0.toml`, `fabv2_public27_b5.toml`: fixed, zero-iteration
  Public-27 comparators with exactly the same 18/9 split, three repeats, and
  execution budget as the Self-Harness study.
- `fabv2_numeric24_self_harness_v5.toml`: corrected 8/8/8 numeric-track
  protocol with a locked scorecard, explicit recovery contract, three repeats,
  and mandatory adaptive-validation improvement.
- `fabv2_numeric24_b5_v5.toml`: hand-engineered V2 prompt under the identical
  V5 execution and split contract.
- `fabv2_case_study_b5.toml`: equal-budget hand-engineered FAB comparator.
- `m2_agentic.toml`, `b5_agentic.toml`, `mvp2_agentic.toml`: earlier agentic
  benchmark stages retained for reproducibility.
- `fabv2_b0.toml`, `fabv2_b5.toml`: broader historical FAB baselines; they do
  not define the bounded three-case protocol.

Validate before spending model tokens:

```bash
uv run self-harness validate configs/<experiment>.toml
uv run self-harness inventory configs/<experiment>.toml
```

Never tune a config after reading its locked-test result and report the result
as if it came from the original protocol. Make a new versioned config instead.
