# FAB v2 public-development benchmark

This directory contains all 27 public questions and rubrics, a frozen numeric
diagnostic, and a Prime-native research runtime. Provenance and hashes are in
`data/manifest.json` and `THIRD_PARTY_NOTICES.md`.

These rubrics are development data, not an untouched test. The local judge is
not Vals' qualitative judge and the key-free tools differ from the official
apparatus. Local scores must never be described as official leaderboard scores.

The evolvable runtime has eight orthogonal surfaces:

- `system.md`: identity and objective;
- `orchestration.md`: budget-aware workflow;
- `tools.md`: capability-use policy;
- `research.md`: source and retrieval strategy;
- `evidence.md`: structured computational memory;
- `subagents.md`: bounded specialist delegation;
- `verification.md`: arithmetic and coverage audit;
- `submission.md`: answer compiler contract.

`workspace/prime_runner.py` starts a new Prime `--no-session` root per case.
The root receives persistent IPython state, evaluator-owned finance tools,
optional RLM specialists, and host-enforced turn/token/time limits. A reserved
no-tool compiler consumes the bounded research trace when the root does not
submit before cutoff. Research and compiler usage are combined.

`configs/fabv2_prime_smoke.toml` is only a cheap integration contract. A full
study requires stratified train/adaptive-validation/locked-scorecard splits,
repeated seeds, and equal-token retry comparators.

Regenerate and verify public artifacts with:

```bash
python benchmarks/fabv2/tools/build_public_data.py --check
```
