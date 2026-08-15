# Coding-project two-loop fixture

This deterministic fixture proves the architecture without spending model
tokens. The product contains a broken `add` function. The inner coding adapter
creates a disposable product copy, invokes `agent.py`, and runs the product's
pytest suite outside the agent process.

The agent only fixes the product when the candidate development harness tells it
to inspect tests. The outer-loop integration test promotes that harness and
verifies that train, validation, and locked-test product copies all pass while
the immutable product seed remains broken.

Run the baseline inventory with:

```bash
uv run self-harness validate configs/coding_demo.toml
```
