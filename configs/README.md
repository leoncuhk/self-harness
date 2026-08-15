# Experiment configurations

Each TOML file freezes the target, model, editable surfaces, data splits,
budgets, gate, and resource ceilings.

- `fabv2_prime_smoke.toml`: three-case Prime runtime integration gate. One
  repeat is never an efficacy claim.
- `coding_demo.toml`: deterministic product-development dual-loop fixture.
- `mvp2_agentic.toml`, `m2_agentic.toml`, `b5_agentic.toml`: generic agentic
  regression fixtures retained for kernel compatibility.

The old FAB official/model-library configs were removed when Prime became the
sole FAB runtime. Historical outcomes remain in `docs/evaluation/`; they are
not executable baselines for the new apparatus.

Validate before spending model tokens:

```bash
uv run self-harness validate configs/<experiment>.toml
uv run self-harness inventory configs/<experiment>.toml
```

Never tune a config after reading its locked scorecard and present the result
as if it came from the original protocol. Create a new versioned contract.
