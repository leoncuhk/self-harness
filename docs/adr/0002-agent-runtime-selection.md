# ADR 0002: Prime inner, atomic Pi outer

- Status: accepted
- Date: 2026-08-15

## Decision

Use Prime Agent for the FAB inner runtime. Use Pi for a single tool-free atomic outer proposal. Keep
the framework-neutral Controller as the sole evaluation and selection authority. DeepAgents is not a
runtime dependency.

## Evidence

Prime supplies capabilities the FAB task uses directly: persistent IPython computation, native
`rlm(...)` specialists, child result delivery and usage attribution, and a long-running research
lifecycle. Pi intentionally has a smaller coding loop and no built-in subagents, so replacing Prime
inside FAB would require rebuilding those capabilities.

The outer task has the opposite shape. The Controller has already bounded and normalized the evidence;
the required output is one falsifiable patch. Two Prime outer attempts consumed roughly 120k–140k
cumulative tokens and produced no surface edit. A tool-using Pi attempt edited three surfaces but hit
132,004 tokens before completing its proposal. Converting Pi to one no-tool atomic response completed
in one call, 17,224 tokens, and 58.7 seconds on the same model route.

## Consequences

- Every case uses a fresh `--no-session` Prime process; persistent state is per rollout, never global.
- Pi cannot browse the workspace or leave partially applied edits. The Controller validates its JSON
  and applies all declared replacements together.
- Runtime popularity is not evidence. Prime/Pi versions and model routes remain recorded in run
  artifacts, and efficacy still depends on candidate evaluation.
- Prime and Pi process isolation is not a security sandbox.

## Sources

- <https://github.com/PrimeIntellect-ai/prime-agent>
- <https://github.com/earendil-works/pi>
