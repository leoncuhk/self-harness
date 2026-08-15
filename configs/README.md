# Experiment contracts

- `coding_demo.toml`: deterministic coding dual-loop fixture.
- `fabv2_smoke.toml`: Prime inner integration, zero evolution.
- `fabv2_evolve_smoke.toml`: one train/validation/scorecard mechanism check.
- `fabv2_minimal.toml`: zero-evolution minimal FAB comparator.
- `fabv2.toml`: Public-27 Numeric-24 8/8/8 development protocol.

Each TOML freezes the target, model, editable surfaces, split assignment, budgets, guards, and gate.
Create a new versioned contract when any of these change; never rewrite a contract after reading its
scorecard and report it as pre-registered.

```bash
uv run self-harness validate configs/<experiment>.toml
uv run self-harness inventory configs/<experiment>.toml
```
