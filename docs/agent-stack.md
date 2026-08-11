# Reference: Deep Agents vs LangChain vs LangGraph

*Distilled from Sydney Runkle, LangChain blog, 2026-08-06 ("Deep Agents vs
LangChain vs LangGraph"). Kept here because this project's inner agent and
proposer both run on this stack.*

## The three layers

One philosophy — builders own the model, the context, and the harness — at three
abstraction levels. Fully composable: any layer can embed any other.

| Layer | Role | Character |
| --- | --- | --- |
| **LangGraph** | agent **runtime** | graph-based; maximal determinism and control; durable execution, HITL, fault tolerance; encode domain knowledge in graph topology |
| **LangChain** | agent **framework** | minimal un-opinionated harness: LLM in a loop calling tools (`create_agent`); **middleware hooks** modify the loop (summarize-when-full, verifiers, approval steps) |
| **Deep Agents** | agent **harness** | opinionated context-engineering bundle (`create_deep_agent`): filesystem backend, subagents, skills, memory; maximal agency |

Key structural fact: **Deep Agents = the core LangChain agent + a bundle of
middleware.** The harness layer is literally implemented as middleware over the
framework layer, and both run on the LangGraph runtime.

## When to reach for each (their rule of thumb)

- **Start with Deep Agents** — capable agent out of the box; drop down only for
  more control. (Their GTM agent runs on it: ~10k req/week, 150 users, 74% of
  traffic ambient/scheduled.)
- **LangChain** when you want the bare loop plus fine-grained control of what
  reaches the model each step (e.g. a RAG Q&A bot needing neither subagents nor a
  filesystem), or you're assembling a bespoke harness.
- **LangGraph** when the workflow doesn't fit a loop or mixes deterministic and
  agentic steps (e.g. extract → score → auto-approve/reject/escalate, where only
  step 1 touches an LLM). Escape hatch when middleware hooks aren't enough.

Determinism↔agency spectrum: LangGraph (max determinism) → LangChain (loop, model
decides each step) → Deep Agents (max agency: summarization + subagents let it run
long and fan out). Middleware is how deterministic steps get injected into the
agentic layers.

Timeline: LangChain 2022-10 → LangGraph 2024-01 (runtime primitives) →
`create_agent` standardizes the loop → Deep Agents 2025-07 (Claude Code/Manus-
inspired general-purpose harness).

## Why this matters for self-harness

- **Our editable surfaces are exactly the Deep Agents bundle**: system prompt,
  tools, skills, middleware (+ subagents and memory as future surfaces). Evolving
  the harness = evolving the layer LangChain itself calls "the harness".
- **Middleware is the highest-leverage surface**: it is where the stack itself
  injects verification, summarization, and approval — i.e. the deterministic
  discipline a proposer would want to add. That the harness layer is "just
  middleware" is direct architectural support for harness-editing as the
  intervention point.
- **Layer choice is itself a harness decision**: a proposer that learns a task is
  better served by a deterministic step than by agency is recapitulating the
  LangGraph-vs-DeepAgents tradeoff. The determinism↔agency spectrum is the design
  space box ③ searches.
- Our loop uses the stack twice: proposer = `create_deep_agent` over a
  `FilesystemBackend` workspace; inner agent = `create_deep_agent` over a per-task
  sandbox, surfaces loaded at call time (`benchmarks/agentic/workspace/agent_harness.py`).
