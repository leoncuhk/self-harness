# FAB v2 Public-27 community protocol

Protocol ID: `fabv2-public27-dev-v1`.

This protocol supports reproducible community research while access to the
private Vals suites is gated. It does **not** create a hidden test from public
questions whose rubrics have already been inspected.

## Tracks

- `reproduction`: official open-source scaffold and official-equivalent tools;
- `open-harness`: custom prompts, tools, memory, middleware, or workflows;
- `oracle`: answers or criterion text were used directly to construct outputs.

Oracle submissions are retained as evaluator/solvability checks and never
ranked as agent capability. Results from the free EDGAR/Yahoo apparatus and the
official paid tool stack must use different `apparatus` identifiers.

## Required comparison

For a Self-Harness claim, run the same frozen model and apparatus under:

1. B0 official prompt;
2. a hand-engineered prompt/policy baseline;
3. equal-total-token retry or best-of-N;
4. sequential refinement when evaluator feedback is available;
5. Self-Harness, with proposer plus rejected-rollout search cost reported.

Use at least three complete repetitions of all 27 questions. Publish the model
version/fingerprint, harness commit/content hash, every per-question outcome,
timeouts/apparatus failures, tokens, dollar cost when known, and wall time.
Question-clustered bootstrap intervals are descriptive; they do not repair
public-set adaptation or establish private-test generalization.

## Judge separation

`judge=official` requires persisted output from the official evaluator. The
local deterministic evaluator must be declared `numeric-diagnostic`. It ignores
qualitative criteria and is useful for search gradients and failure analysis,
not for an official partial-credit claim. The builder refuses to mix the two
tables.

## Selection discipline

The 27 questions form nine categories with three examples each. During
development, rotate which within-category example is hidden from the proposer
(three 18/9 folds), and disclose that all folds remain public and adaptive.
Choose the final harness and budgets before requesting Vals private Validation.
Only that licensed set can support a fresh selection estimate; only Vals' Test
result can support an official leaderboard comparison.

Build a table from one or more completed submission JSON files:

```bash
uv run python scripts/build_fabv2_leaderboard.py submissions/*.json \
  --output leaderboard.md
```

`submission.example.json` documents the shape but is intentionally incomplete
and must not be reported as a result.

`evidence/codex_hard4_v1.json` is a machine-readable, hash-pinned summary of the
targeted hard-4 diagnostic discussed in the case study. It explicitly records
that the sequence was human-directed, did not use the autonomous proposer, did
not complete Public-27, and is not leaderboard-eligible. It is evidence, not a
community submission.
