# ADR 0002: Prime inner runtime, measured outer runtime

- Status: accepted for inner; outer A/B in progress
- Date: 2026-08-15

## Decision

Use Prime Agent as the FAB inner runtime. Keep the Self-Harness Controller as
the only selection authority. Compare Prime and Pi under contract-matched outer
proposer smoke runs; promote a default outer runtime only from measured proposal
completion, accepted validation gain, resource use, and lifecycle reliability.

## Evidence

Prime Agent 0.7.2 (`97b994c3`) provides the capabilities the FAB inner loop
actually needs: a persistent IPython computational state, native `rlm(...)`
children, agent-to-agent result delivery, child usage attribution, and a
continual-harness model. Real runs also exposed lifecycle defects that the host
adapter now handles: ineffective native token bounds for some tool loops, Unix
socket path limits, complete `text_end` without `message_end`, and daemon
`exit 0 / 0 events`.

Pi 0.73.0 is installed locally and its current upstream at audit time is
`earendil-works/pi@086c32e7`. Pi has a smaller four-tool coding loop, clean JSON,
RPC, and SDK embedding. Its official documentation explicitly omits built-in
subagents. A live same-route probe produced a complete `PI_OK` lifecycle with
authoritative usage. That makes Pi a credible outer proposer, where the task is
bounded file inspection and editing, but a regression for the FAB inner RLM
unless this project rebuilds persistent computation and delegation itself.

## Consequences

- FAB inner stays Prime-first; Pi is not a replacement selected by popularity.
- Both proposer adapters share one host process boundary and one controller.
- `fabv2_prime_evolve_smoke.toml` and `fabv2_pi_evolve_smoke.toml` differ only
  in outer runtime.
- Neither runtime may edit the evaluator, split, model, budget, gate, or archive.
- Prime `/refine` and Pi extensions are not allowed to become hidden selection
  loops.

## Selection rule

Prefer the runtime that first produces a valid bounded proposal and then yields
the stronger non-regressing adaptive-validation result at equal frozen budgets.
If efficacy ties, prefer fewer apparatus failures, lower tokens/latency, and the
simpler lifecycle. One smoke run is enough to reject a broken integration, not
enough to establish a universal winner.

## Sources

- <https://github.com/PrimeIntellect-ai/prime-agent/tree/97b994c3d7c45ca1ae635190e91e9e58ddf2577c>
- <https://github.com/earendil-works/pi/tree/086c32e74530564922d011ade23ff582c9d63116>
- Prime `packages/coding-agent/docs/rlm.md`
- Pi `packages/coding-agent/README.md`, `docs/json.md`, and `docs/sdk.md`
