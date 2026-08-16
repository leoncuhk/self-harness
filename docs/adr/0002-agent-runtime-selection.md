# ADR 0002: Replaceable inner and atomic Pi outer adapters

- Status: accepted
- Date: 2026-08-15

## Decision

Support Prime Agent and Codex CLI as formal FAB inner adapters. Prime remains the research baseline;
Codex is the current high-capability path and produced the best measured hard-case result. Select
the inner runtime in the fingerprinted experiment environment. Use Pi as the current single-call,
tool-free outer proposal adapter. Keep the framework-neutral Controller as the sole evaluation and
selection authority. DeepAgents is not a runtime dependency.

## Evidence

Prime supplies capabilities the FAB task uses directly: persistent IPython computation, native
`rlm(...)` specialists, child result delivery and usage attribution, and a long-running research
lifecycle. Pi intentionally has a smaller coding loop and no built-in subagents, so replacing Prime
inside FAB would require rebuilding those capabilities.

Codex lacks Prime's native persistent RLM lifecycle, but provides a stronger coding/research agent
and directly consumes the project harness through `AGENTS.md`. Both adapters use case-local
workspaces, the same evaluator-owned tools, and the same evaluator return shape. Codex CLI exposes
wall-time control but no equivalent hard token/turn ceilings, which remain measured post hoc.

The outer task has the opposite shape. The Controller has already bounded and normalized the evidence;
the required output is one falsifiable patch. Two Prime outer attempts consumed roughly 120k–140k
cumulative tokens and produced no surface edit. A tool-using Pi attempt edited three surfaces but hit
132,004 tokens before completing its proposal. Converting Pi to one no-tool atomic response completed
in one call, 17,224 tokens, and 58.7 seconds on the same model route.

## Consequences

- Every case uses a fresh `--no-session` Prime process; persistent state is per rollout, never global.
- Every Codex case uses a fresh ephemeral process and case-local workspace.
- Pi cannot browse the workspace or leave partially applied edits. The Controller validates its JSON
  and applies all declared replacements together.
- Runtime popularity is not evidence. Prime/Pi versions and model routes remain recorded in run
  artifacts, and efficacy still depends on candidate evaluation.
- Prime and Pi process isolation is not a security sandbox.
- Changing Prime to Codex still defines a different experimental arm; runtime selection never
  establishes self-harness efficacy by itself.
- Domain structure and frozen data access belong to the controller/benchmark contract, not to a
  framework. See ADR 0003.

## Sources

- <https://github.com/PrimeIntellect-ai/prime-agent>
- <https://github.com/earendil-works/pi>
