# Gaps and roadmap

*Where this implementation stands against the 2026 literature, and what to build
next, in dependency order. Claims here are sourced from [paper-study.md](paper-study.md);
status is sourced from the code.*

## Standing

Two things are true at once, and both matter:

**Ahead of the literature on evaluation.** The equal-budget B1 arm, the third
split that is genuinely sealed (both 2606.09498 and Evo-Bench let held-out
participate in promotion), the B5 mature-harness baseline, the prediction ledger,
the static anti-gaming guard, and a pre-registration whose stop rule has actually
fired — no published harness-evolution result carries this set.

**Behind the literature on diagnosis.** Every positive result in the field feeds
its proposer **execution traces**. This repo feeds it pytest assertion text. The
one thing all the negative results share is honest budget matching; the one thing
all the positive results share is trace-grounded diagnosis. Nobody has published
both together. That is the opening.

## The gaps

Ordered by leverage, not by effort.

| # | Gap | Evidence it matters | Status in code |
| --- | --- | --- | --- |
| 1 | **No experience observability** — inner trajectories are discarded | AHE's middle pillar; every positive result reads traces | `run_task` returns tokens / message count / fingerprints only; `train_failures.json` carries `failure_message` alone |
| 2 | **Tasks not selected by measured harness sensitivity** | Evo-Bench Task-Harness Response Map; MVP-1 died of exactly this | strata authored by hand; `B5 == seed` is a one-probe sensitivity alarm we read *after* the fact |
| 3 | **No long-term-memory surface** | AHE ablation: gains sit in tools / middleware / **memory**, not prompt | 4 surfaces: prompt, tools, skills, middleware |
| 4 | **No archive, no anytime-best, no negative-result reuse** | Evo-Bench: early saturation + never rolling back is the dominant failure; Lil'Log requirement 4 | greedy `_select_winner`; rejected candidates land in `decision.json` but never re-enter proposer context |
| 5 | **No checkpoint/resume; inner agent has no retry** | three dead MVP-2 M3 runs | retries cover the proposer path only; a crash at iteration 3 discards every prior rollout |
| 6 | **B1 is the wrong strongest arm for a deterministic-verifier suite** | 2607.12227: sequential refinement 91.8 vs evolution 86.2 with unit tests | M4 registers oracle best-of-N only |
| 7 | **Feedback budget never stated, only inference budget** | 2607.12227 holds both axes equal | M4 matches tokens; B1 reads pass/fail, evolution reads per-case failure text — not the same feedback |
| 8 | **No prequential (forward) scoring** | TTHE's own admitted limitation — an open gap in the field | iteration *t*'s harness is never scored on iteration *t+1*'s cases before adapting |

Gaps 6 and 7 change what MVP-2's result can claim and therefore need a
pre-registration amendment, not just code — see *Protocol consequences* below.

## Build order

**A — survive long runs** *(prerequisite for everything; nothing else is
reachable while M3 cannot finish)*

- A1 retry + per-request timeout in `agent_harness.run_task`; reuse the existing
  transient-error classifier rather than writing a second one
- A2 **run-level `--resume`**: results already land under
  `variants/<key>/<split>/`, so skipping complete `(variant, split, repeat)`
  triples is a small change with the largest single payoff
- A3 stage logs emit markers only — the scorecard-leak lesson turned into code

**B — experience observability** *(the highest-leverage change in this document)*

- B1 persist inner trajectories as JSONL: tool name, arguments, error, truncated
  output, step index
- B2 compute φ(r) from the trajectory (tool-call patterns, retry loops, delivery
  without verification); demote assertion text to a secondary signal
- B3 add `traces/` to the proposer workspace, **bounded** — one representative
  trajectory per failure cluster, preserving the bounded-proposal-context property
- B4 feed rejected candidates and their rejection reasons back into the proposer

After B, box ② performs diagnosis for the first time instead of regex-matching
error strings. The `unknown` rate in signature clusters is the metric that says
whether it worked.

**C — surfaces that the ablations say carry gains** *(ship with D)*

- C1 `memory` — a long-term memory file plus its read/write policy
- C2 `runtime_policy` — error caps, tool-message caps, recursion limit
- C3 `subagents` — declared sub-agent roles

**D — a testbed that can detect anything**

1. **Evo-Bench (2608.09096)** — public code and data, 608 tasks pre-filtered for
   harness sensitivity, response-matched splits, sealed evaluation. Buys external
   comparability and removes the designer=runner bias in one move. *Recommended.*
2. TB2.1 via harbor — the original confirmatory step; still costs the custom
   harbor agent that Amendment 1 deferred.
3. Authoring tasks again requires the sensitivity probe first: 3–4 deliberately
   different harnesses × all candidate tasks, keep only measured Sens>0 with
   headroom, assign splits by response distribution rather than alphabetically.

**E — selection layer**

- E1 Anytime Validation Score (best-so-far curve; derivable from existing
  `decision.json` history)
- E2 archive + rollback to the historical best
- E3 K candidates by **objective** (remove constraints / add tooling / add a
  verification step), TTHE-style, instead of round-robin over clusters

**F — evaluation protocol**

- F1 add the **sequential-refinement** arm; on deterministic verifiers it, not
  best-of-N, is the arm that decides the claim
- F2 **prequential scoring** — score iteration *t*'s harness on iteration *t+1*'s
  cases before it adapts; cheap here, and unfilled in the literature
- F3 cross-policy transfer matrix (updater × beneficiary) — Evo-Bench reports
  positive transfer, 2606.09498 reports model-specificity; worth an independent read

Recommended path: **A → B → D1**, with C alongside D, then E and F.

## Protocol consequences

- Gaps 6 and 7 mean MVP-2's M4, as frozen, tests the weaker of the two available
  baselines and does not state its feedback budget. The frozen rule stands for
  MVP-2 — it may be reported against, not renegotiated — and the writeup must
  disclose both limits explicitly. A sequential-refinement arm and a two-axis
  budget statement belong in the **next** pre-registration, not this one.
- Everything in B changes what the proposer sees, so it cannot land mid-run. It
  is an MVP-3 change; MVP-2 finishes on the current information set or is
  reported as unfinished.
