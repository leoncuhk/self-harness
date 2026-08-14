# Experiment configurations

Each TOML file is an executable experiment contract, not merely runtime
configuration. It fixes the target workspace, model, editable surfaces, data
splits, proposer budget, evaluation budget, gate, and resource ceilings.

- `coding_demo.toml`: deterministic product-development dual-loop fixture.
- `fabv2_self_harness.toml`: bounded FAB v2 structural self-harness study.
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
