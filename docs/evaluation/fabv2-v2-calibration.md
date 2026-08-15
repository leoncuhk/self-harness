# FAB v2 v2-objective calibration

Run: `runs/fabv2-v2-calibration`, executed 2026-08-15. The run directory is
ignored by Git and must accompany any external claim as raw evidence.

## Frozen effective contract

- model and proposer: `openai/deepseek-v4-flash`;
- one train case q004, one adaptive-validation case q012, one scorecard case q019;
- one repeat, one candidate, one iteration;
- eight turns, 600-second agent limit, 780-second outer case limit;
- primary objective: numeric-diagnostic `ungated_credit`;
- official-shaped dealbreaker partial credit retained only as a reported metric.

The time limits were raised from 360/480 after the first q012 attempt ended as
`apparatus:case_timeout` without producing a measurement. No q012 outcome had
been observed. The evaluation-contract fingerprint then forced both baseline
cases to rerun under the new contract.

## Result

| Arm | q004 train ungated | q012 validation ungated | q019 scorecard ungated | Passes |
| --- | ---: | ---: | ---: | ---: |
| Seed | 0.000 | 0.000 | 0.000 | 0/3 |
| Candidate | 0.000 | 0.000 | not run separately | 0/2 |
| Selected final | 0.000 | 0.000 | 0.000 | 0/3 |

Candidate `iter-001` changed all four prompt/policy surfaces and was rejected:
`Δtrain=0`, `Δvalidation=0`. Every measured rollout stopped at the eight-turn
limit with an empty final answer. The candidate added turn budgeting and a
submit-before-exhaustion policy, but still failed to submit within eight turns.

| Cost component | Provider tokens | Wall time |
| --- | ---: | ---: |
| Selected seed/final measurement (q004/q012/q019) | 206,744 | 701.5s |
| Candidate optimization rollouts (q004/q012) | 139,650 | 708.1s |
| Outer proposer | 1,299,282 | not reported |
| Total measured provider tokens | 1,645,676 | at least 1,409.6s |

The table excludes failed apparatus-calibration attempts. They are operational
cost, but one timed-out q012 call did not persist complete token accounting.

## What this establishes

- the v2 continuous metric is executable end to end;
- a non-improving structural edit is conservatively rejected;
- eight turns are an invalid efficacy regime for this model/apparatus because
  all outputs are censored before submission;
- one-repeat results are highly unstable: an earlier q004 apparatus-calibration
  path submitted an answer and reached ungated credit 0.286, while the frozen
  effective-contract q004 run exhausted its turns and scored 0.

It does not establish a FAB improvement, a Public-27 rank, generalization, or an
optimal harness. `configs/fabv2_self_harness_v3.toml` preregisters a 14-turn
successor rather than silently changing v2 after seeing this result.

## Instrumentation findings

The run exposed three bugs now fixed in source:

1. unmeasurable apparatus results were reusable after environment repair;
2. resume validity ignored the evaluation contract and compared only harness
   content;
3. prediction JSON containing `{{document_key}}` was truncated by the fence
   parser.

It also exposed stale trajectory retention after a non-reusable rerun. The v2
candidate diagnosis therefore read both the old 360-second and current
600-second q004 trajectories. The candidate was rejected, so the selected
harness is unaffected; future invalidated split directories are cleared before
re-execution.
