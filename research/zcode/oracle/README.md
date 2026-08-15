# Contaminated oracle material

Everything in this directory is answer-aware or derived from answer-aware
evaluation. It is valuable for rubric interpretation, evaluator debugging, and
historical audit, but it is **not valid blind evidence**.

Hard rules:

1. no path in this tree may appear in an experiment config;
2. the outer-loop proposer must never receive these files or their contents;
3. `historical/*.json` is stale, non-comparable debug output, not leaderboard
   evidence;
4. Public-27 claims must be regenerated from the frozen benchmark protocol and
   published run artifacts.

