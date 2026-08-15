# FAB v2 / ZCodeProject audit and evidence plan

Audit date: 2026-08-15. The comparison target is
`/Users/leon/ZCodeProject`; claims below distinguish repository inspection,
official public evidence, and proposed work.

## Bottom line

The current repository implements a real L3 Self-Harness loop, but it has **not
demonstrated a FAB v2 improvement, much less the highest level**. Its strongest
evidence is orchestration correctness and conservative rejection: the executed
three-question v1 run scored 0 for the seed, B5, and final arm; the later v2
continuous-objective calibration also scored 0 and rejected its candidate.
Those are valid negative results, not leaderboard results.

ZCodeProject is highly useful as a source of the complete public dataset,
official scaffold semantics, category taxonomy, source-research experience, and
candidate policies. Its answer-aware files and historical score files are not
valid blind evaluation evidence. The 27 official public questions have now been
integrated with source commit and SHA-256 provenance; answer files were not.

## Evidence grades

| Question | Verdict | Evidence |
| --- | --- | --- |
| Is Self-Harness structurally implemented? | Yes | isolated inner/outer loops, frozen evaluator/goal, editable-surface allowlist, repeated evaluation, conservative/objective gates, cost veto, traces, prediction ledger, archive, resume, artifact audit, deterministic E2E |
| Has it improved FAB v2? | No observed gain | both bounded v1 and v2 rejected their candidate with zero selected-arm gain |
| Is the v2 continuous objective validated live? | Yes, negatively | the loop executed, but every eight-turn rollout exhausted its budget with an empty answer and zero credit |
| Is Public-27 available locally? | Yes | official CSV SHA-256 pinned; 27 questions, 239 criteria, 79 must-pass, nine categories |
| Is the local score official FAB partial credit? | No | the local deterministic judge cannot decide qualitative criteria and uses free/non-identical tools |
| Is there an auditable ranking mechanism? | Yes, locally | candidate archive plus the new Public-27 submission contract and separate official/diagnostic tables |
| Is there a credible community leaderboard result yet? | No | no complete three-repeat 27-question submission exists |
| Is this recursive self-improvement? | Related, weak form | the harness edits an artifact around frozen weights (L3); no compounding improvement of the improver has been shown |

## What ZCodeProject contributes

| Asset | Use | Integration decision |
| --- | --- | --- |
| `finance-agent-v2/data/public.csv` | canonical 27 public questions and rubrics | integrated and hash-pinned under `benchmarks/fabv2/data/` |
| `finance_agent/get_agent.py`, `prompt.py`, `tools.py` | official loop, prompt, tool contracts, limits | compare continuously; current free runner documents deviations |
| `SYSTEM_PROMPT_V2.md` | strong hand-engineered comparator | already represented by `prompt_v2.txt`; comparator, not proof of self-improvement |
| category and rubric analysis | stratification and failure taxonomy | use for Public-27 folds and diagnostic reports |
| `tools_local.py` | EDGAR/sec.gov/Yahoo free-tool prototype | useful implementation reference; not apparatus-equivalent to Tavily/sec-api/Tiingo |
| `solutions/*.md`, `solutions/answers.json` | source-discovery and evaluator debugging | quarantined under `research/zcode/oracle/`; any use makes an experiment oracle/answer-aware |
| `judge.py` | deterministic numeric smoke signal | concept retained, relabeled diagnostic; not an official score |
| `scores.json`, `selftest_scores.json` | historical/debug artifacts | preserved under `research/zcode/oracle/historical/`, isolated from ranking because provenance and judge limitations prevent comparison |
| playbook claims and proposed paper text | hypotheses and experiment ideas | require independent reproduction before citation |
| caches, virtualenvs, secrets | none | never integrate |

Two specific ZCode claims were falsified or weakened by inspection:

1. Its judge excludes unknown qualitative criteria from the denominator and
   gates only on known numeric must-pass criteria. The output is neither a full
   rubric score nor a dependable “upper bound” when omitted qualitative
   dealbreakers can zero the official score.
2. Concatenating rubric text into a “perfect answer” proves anchor extraction,
   not autonomous research or answer quality. Twenty-one saved successful
   answer records do not become blind results after their rubrics/solutions have
   been used in development.

## Official facts checked

The Vals FAB v2 page, updated 2026-08-14 when inspected, states:

- Public: 27 open-source samples;
- Private Validation: 450 samples available for license;
- Test: 450 private samples, used for results on the official page;
- the public set and agent harness are open source.

The current official page's leading overall entry was 60.599 for
`meta/muse_spark_1_2`. That score is private-Test evidence under Vals' harness;
it is not directly comparable to a local free-tool numeric diagnostic. The
official GitHub README permits local harness/model modification and links to the
SDK, but neither the page nor repository inspected here confirms the stronger
claim that a public custom-scaffold leaderboard submission channel is already
open or formally scheduled. Treat that as unverified until Vals publishes a
submission contract.

Sources:

- <https://www.vals.ai/benchmarks/fabv2>
- <https://github.com/vals-ai/finance-agent-v2>
- source commit `b979786a8f9c49c178a88720ea4bb6fb16cbf818`

## Correct Public-27 scientific claim

Call the result **“FAB v2 Public-27 Development”**, never “official FAB v2,”
“hidden test,” or “best FAB v2.” All public examples are development data once
their rubrics are inspected. The useful claims are narrower:

- exact reproducibility on a pinned public artifact;
- within-apparatus comparisons under identical model and budget;
- whether a frozen Self-Harness protocol beats declared B0/B5 and equal-budget
  sampling/refinement comparators;
- per-category failure patterns and search efficiency;
- transfer hypotheses to be tested later on licensed Validation.

The protocol requires three complete repeats, question-clustered bootstrap
intervals, full per-question artifacts, apparatus failures, model/harness
fingerprints, evaluation cost, and total search cost. The supplied three 18/9
folds rotate one public question per category behind the proposer, but remain
adaptive development folds. The final public result should evaluate the frozen
harness on all 27 and disclose every prior exposure.

## Highest-priority gaps

1. **Evaluator fidelity:** 65 of 239 criteria are qualitative; two General
   Qualitative questions have no numeric criteria at all. Numeric-only search
   can optimize the wrong target. A calibrated qualitative judge, validated
   against human/official labels, is more important than another proposer.
2. **Apparatus fidelity:** local web search is a stub and the remaining free
   services differ from the official tools. Report both apparatus profiles;
   never pool them.
3. **Efficacy evidence:** run the preregistered v3 and later Public-27 protocols
   across at least three repeats. The existing one-repeat, three-case results
   only test integration and revealed eight-turn censoring.
4. **Comparator strength:** fixed B0/B5, token-matched retry/best-of-N, and
   sequential refinement must precede an automated-evolution claim.
5. **Contamination:** criterion text is public and failure messages expose
   failed criteria. The complete composed harness is now checked for exact
   8-word rubric shingles, but semantic memorization remains possible and must
   be disclosed.
6. **Transfer:** only licensed Validation, a later fresh benchmark, or a new
   model/project can test generalization. Public-fold rotation is not a
   substitute.

## LGBO: useful principle, not a drop-in theorem

LGBO (arXiv:2605.17976v1, ICLR 2026) repeatedly injects an LLM preference as a
mean shift into a Bayesian-optimization surrogate while leaving covariance and
the acquisition decision intact. Its transferable lesson is separation of
roles: **the LLM supplies a soft search prior; measured uncertainty and the
external objective retain control**.

For harness evolution, a future cost-aware scheduler should represent proposals
by strategy family (retrieval, planning, calculation, verification, submission,
memory, tool/middleware), changed surfaces, targeted failure cluster, predicted
gain, regression risk, and estimated cost. A practical acquisition rule is:

```text
acquisition = expected_gain / expected_cost
            + uncertainty_bonus
            + calibrated_LLM_preference
            - regression_risk
```

The preference weight should shrink when the prediction ledger has low precision
and retain explicit exploration outside preferred families. Start with a
categorical Bayesian bandit or TPE-style scheduler; do not fit a Gaussian process
to a handful of edits. This repository has one FAB candidate, so implementing a
surrogate now would add ceremony without learnable evidence. First collect a
minimum multi-family candidate archive, then preregister and compare the
scheduler against round-robin cluster targeting.

LGBO's regret guarantee does not transfer directly: harness edits are discrete,
structured, nonstationary, conditional on history, noisy, multi-objective, and
can change the future representation itself. The paper's frozen/preference
assumptions and GP geometry therefore remain inspiration, not proof for this
system.

## Low-entropy field model

Autoresearch, LLM Wiki, AlphaEvolve/ShinkaEvolve, Self-Harness, and stronger RSI
share the same external loop:

```text
mutable state -> propose -> execute -> external measurement -> select -> retain
```

They differ in what mutates (experiment, knowledge artifact, program, harness,
or weights) and what the optimizer cannot rewrite. “Automation” applies to both
search and mechanical evaluation; validity still comes from an external anchor.
If the optimizer can rewrite its goal, verifier, private data, or budget, the
measured improvement loses meaning.

Self-Harness is therefore inside the recursive-improvement family, but current
evidence supports recursive **artifact** improvement only. Strong RSI requires
reliable compounding: an improved system must become better at producing its
next improvement under controlled, equal-budget evaluation. Neither a single
accepted edit nor repeated benchmark search establishes that property.

## Execution order

1. run and audit the bounded v3 budget before scaling;
2. calibrate qualitative judging on a human-labeled subset;
3. execute fixed B0/B5 and equal-budget refinement arms;
4. execute `fabv2_public27_self_harness.toml` only after cost estimation;
5. publish complete Public-27 development artifacts through the community
   submission schema;
6. freeze the harness, then seek licensed Validation access;
7. add the LGBO-inspired scheduler only when the archive can estimate family
   gain, uncertainty, regression, and cost.
