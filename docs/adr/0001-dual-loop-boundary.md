# ADR 0001: Separate product edits from harness evolution

- Status: accepted
- Date: 2026-08-15

## Decision

Run product edits in disposable inner-loop workspaces. Run harness candidates
in a separate outer-loop lineage. CI, private cases, budgets, and promotion are
owned by the immutable control plane.

## Why

Mixing product and harness edits makes attribution impossible: a higher score
could come from a better development policy, a task-specific product patch, a
weaker test, or extra compute. Separate lineages make each claim replayable and
allow both products and harnesses to be rolled back independently.

## Consequences

- A coding adapter needs an explicit command and artifact protocol.
- Every candidate is replayed from the same product seed.
- Inner product commits never mutate the harness repository.
- Evaluator changes require a new experiment contract, never a candidate edit.
