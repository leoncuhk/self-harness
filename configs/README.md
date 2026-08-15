# Experiment contracts

- `coding_demo.toml`: deterministic coding dual-loop fixture.
- `fabv2_smoke.toml`: Prime inner integration, zero evolution.
- `fabv2_evolve_smoke.toml`: one train/validation/scorecard mechanism check.
- `fabv2_replicate_strong.toml`: three-repeat strong-seed comparator on the preflight cases.
- `fabv2_evolve_runtime.toml`: three-repeat outer loop with compiler headroom and machine tool-output policy.
- `fabv2_evolve_replicated.toml`: three-repeat live evolution contract; use this for promotion claims.
- `fabv2_public27_strong.toml`: frozen strong harness, Public-27 × three-repeat publication arm.
- `fabv2_replicate_evolved.toml`: three-repeat replication of the accepted preflight candidate.
- `fabv2_replicate_contender_v3.toml`: independent current-protocol replication of the v3 automatic contender.
- `fabv2_minimal.toml`: zero-evolution minimal FAB comparator.
- `fabv2.toml`: Public-27 Numeric-24 8/8/8 development protocol.

Each TOML freezes the target, model, editable surfaces, split assignment, budgets, guards, and gate.
Create a new versioned contract when any of these change; never rewrite a contract after reading its
scorecard and report it as pre-registered.

```bash
uv run self-harness validate configs/<experiment>.toml
uv run self-harness inventory configs/<experiment>.toml
```
