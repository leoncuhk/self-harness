# FAB v2 Numeric-24 V5 protocol

## Objective

V5 tests one precise claim:

> With DeepSeek V4 Flash, frozen tools, and a fixed per-question execution
> budget, can the outer Self-Harness loop automatically produce a harness that
> beats the official seed, survives adaptive validation, and remains better on a
> once-opened locked scorecard?

This operationalizes the ML-to-Agent mapping:

| ML workflow | Agent/Self-Harness equivalent | Repository boundary |
| --- | --- | --- |
| collect and label data | build train/validation/scorecard eval cases | frozen evaluator and split manifest |
| train model weights | evolve prompt, research, verification, submission policies | editable harness surfaces |
| offline evaluation | replay the same Agent under the frozen contract | runner, repeats, objective gate |
| inference | execute the finance Agent on one question | inner loop |
| drift/serving monitoring | trace behavior, errors, recovery, tokens and latency | evidence and telemetry planes |

The model weights stay frozen. Improvement means better external scaffolding,
not a stronger endpoint, larger context budget, evaluator access, or hidden
answer injection.

## Why Numeric-24, not the old Public-27 config

The local deterministic judge cannot evaluate qualitative rubric criteria.
Questions q001 and q003 have no numeric criterion, and q002 is predominantly
qualitative. Scoring those as fixed zeros creates the appearance of a full FAB
score while supplying no optimization signal.

V5 therefore uses q004-q027: 24 public questions across eight categories. Each
category contributes one train, one adaptive-validation, and one locked-scorecard
question. This is a numeric-research development track, not full FAB v2 and not
an official Vals score.

The older Public-27 protocol also imposed `rubric_numeric_coverage >= 0.75`.
Coverage is fixed by the rubric, not by the answer, and its holdout mean is
0.627. That gate was mathematically impossible to satisfy. V5 removes it.

## Frozen experiment

- B0: official upstream prompt; additional policy surfaces are empty.
- B5: fixed hand-engineered V2 prompt.
- Self-Harness: B0 seed plus four editable surfaces.
- Model: `openai/deepseek-v4-flash` for both inner and outer agents.
- Per-question main budget: 14 turns, 900 seconds, 8,000 output tokens per call.
- Recovery: at most 3 submit-only turns / 120 seconds, explicitly fingerprinted
  and fully included in accounting.
- Timeout ordering: 900-second main phase, then recovery within a 1,050-second
  pytest ceiling, then a 1,080-second outer-process ceiling. Earlier equal
  900-second Agent/pytest limits killed the test before time-based recovery.
- Repeats: 3 per question per evaluated harness.
- Split: 8 train / 8 adaptive validation / 8 locked scorecard.
- Promotion: both train and validation must be non-degrading; validation must
  improve by more than 0.03 `ungated_credit`; stable binary passes cannot regress.
- Cost veto: normalized serving tokens and latency may grow by at most 1.25×.
- Scorecard: baseline and final only, after all promotion decisions.

“Optimal” means the best validated candidate found inside this declared search
budget. It does not mean a global optimum over all prompts, tools, models, or
private FAB questions.

The evolution arm has a worst-case 240 inner rollouts: 48 for the repeated B0
train/validation baseline, 144 for three candidates, and 48 for baseline/final
scorecards. Ten canonical V4 rollouts averaged about 154,967 recorded tokens and
210 seconds, projecting roughly 37.2M inner tokens and 14 serial hours before B5,
retry, and outer-proposer spend. This is a planning estimate, not a V5 result.

## Execution stages

Run a one-repeat dry stage first. It validates infrastructure and estimates cost;
its scores are not V5 evidence:

```bash
uv run self-harness run configs/fabv2_numeric24_self_harness_v5.toml \
  --output-dir runs/fabv2-v5-dry --max-iterations 0 --repeats 1
uv run python scripts/verify_artifacts.py runs/fabv2-v5-dry
```

Then execute the frozen arms without changing the config:

```bash
uv run self-harness run configs/fabv2_numeric24_self_harness_v5.toml \
  --output-dir runs/fabv2-v5-evolve
uv run self-harness run configs/fabv2_numeric24_b5_v5.toml \
  --output-dir runs/fabv2-v5-b5
```

After the evolution spend is known, run the official seed with enough repeats
to approximate the same total token budget. This is an oracle best-of-N upper
bound, not a deployable selector:

```bash
uv run self-harness run configs/fabv2_numeric24_self_harness_v5.toml \
  --output-dir runs/fabv2-v5-retry --max-iterations 0 --repeats <N>
```

Finally audit and compare:

```bash
uv run python scripts/verify_artifacts.py \
  runs/fabv2-v5-evolve runs/fabv2-v5-b5 runs/fabv2-v5-retry
uv run python scripts/compare_fabv2_v5.py \
  --evolved-run runs/fabv2-v5-evolve \
  --b5-run runs/fabv2-v5-b5 \
  --retry-run runs/fabv2-v5-retry \
  --output docs/evaluation/fabv2-v5-results.md
```

## Evidence thresholds

The Self-Harness efficacy claim passes only when all are true:

1. validation improves over B0 by more than 0.03 with no train regression;
2. locked scorecard improves over B0 and is not below B5;
3. no apparatus failure or model fingerprint drift invalidates the stage;
4. serving cost remains within the 1.25× veto;
5. the result is reported next to the token-matched retry oracle, including all
   outer-search and rejected-candidate spend.

Failure of any item is a valid negative result. The system must not weaken the
gate, reshuffle scorecard questions, or silently raise the budget after seeing it.

## Implementation smoke, 2026-08-15

A real one-turn q004 run deliberately forced recovery and confirmed the merged
accounting contract:

| Field | Observed |
| --- | ---: |
| Main tokens | 3,299 |
| Recovery tokens | 2,550 |
| Total tokens | 5,849 |
| Main + recovery turns | 2 |
| Tool usage | calculator 2, submit 1 |
| Stop reason | `max_turns+recovery_submit` |

The answer failed the rubric, as expected under a one-turn research budget; this
was an execution-contract test, not efficacy evidence. The preceding full-budget
attempt exposed the pytest/Agent timeout race at 900.014 seconds and was discarded
as an incomplete apparatus run after the defect was fixed.
