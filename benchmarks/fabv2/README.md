# FAB v2 benchmark adapter

This directory contains the assets needed for an unofficial Public-27 study:

- `data/` and `questions.json`: public questions and provenance;
- `evals/frozen/`: numeric rubric judge and telemetry, unavailable to the proposer;
- `harnesses/minimal/` and `harnesses/strong/`: contract-matched starting points;
- `workspace/`: Prime inner runner, evaluator-owned finance tools, and model provider;
- `community/`: public fold and submission metadata;
- `contracts/diagnostics.toml`: frozen finance failure layers and non-causal routing facets.

The former FAB/model-library harness is intentionally absent. Prime executes a fresh `--no-session`
rollout with private persistent computation, optional RLM specialists, evidence memory, verification,
and a no-tool compiler. `search-page` scans complete long filings while returning bounded context;
`fetch-page` intentionally returns a prefix.

`workspace/market_data.json` and `workspace/sec_data.json` are small evaluator-owned examples of a
versioned data plane. They preserve official-source observations needed when a ticker is delisted or
a historical endpoint disappears, and their content changes the evaluation fingerprint. The SEC
document record stores a bounded verbatim excerpt plus the full-source SHA-256. These fixtures cover
the diagnosed GTLS facts only; other Public-27 source retrieval may still use the local ignored HTTP
cache or live network and must not be described as fully frozen.

Public rubrics make results reproducible but not blind. Use `configs/fabv2.toml` for the frozen 8/8/8
development protocol and describe any result as an unofficial community evaluation.
