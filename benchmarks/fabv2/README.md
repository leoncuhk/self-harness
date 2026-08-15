# FAB v2 benchmark adapter

This directory contains the assets needed for an unofficial Public-27 study:

- `data/` and `questions.json`: public questions and provenance;
- `evals/frozen/`: numeric rubric judge and telemetry, unavailable to the proposer;
- `harnesses/minimal/` and `harnesses/strong/`: contract-matched starting points;
- `workspace/`: Prime inner runner, evaluator-owned finance tools, and model provider;
- `community/`: public fold and submission metadata.

The former FAB/model-library harness is intentionally absent. Prime executes a fresh `--no-session`
rollout with private persistent computation, optional RLM specialists, evidence memory, verification,
and a no-tool compiler. `search-page` scans complete long filings while returning bounded context;
`fetch-page` intentionally returns a prefix.

Public rubrics make results reproducible but not blind. Use `configs/fabv2.toml` for the frozen 8/8/8
development protocol and describe any result as an unofficial community evaluation.
