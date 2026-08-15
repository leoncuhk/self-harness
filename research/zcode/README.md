# ZCodeProject preservation archive

Preserved on 2026-08-15 before `/Users/leon/ZCodeProject` is retired. This copy
contains all non-generated, locally unique FAB v2 playbook material plus the
small official `finance-agent-v2` source snapshot on which the analysis was
based. Caches, virtual environments, bytecode, nested Git metadata, and secrets
were deliberately excluded.

## Layout and trust boundary

| Path | Contents | Permitted use |
|---|---|---|
| `playbook/` | Seven Chinese research notes and the V2 prompt | design review and historical analysis |
| `tools/` | local rubric builder, judge stub, and tool prototype | reference only; not the frozen evaluator |
| `oracle/` | answer-aware solutions, rubrics, and historical scores | evaluator debugging and source analysis only |
| `upstream/finance-agent-v2/` | exact MIT-licensed upstream Git snapshot | contract comparison and reproduction |
| `upstream/model-library/` | reproducibility manifest for a clean public dependency | fetch the exact dependency state |

The executable Public-27 dataset remains at
`benchmarks/fabv2/data/public.csv`. Its duplicate inside the upstream snapshot
is retained intentionally because that directory is an exact source snapshot;
both files have SHA-256
`27b48c08a6099bc076b4194cac7cefe295082b9aedcbc67f4fedfa70468b427e`.

## Provenance

- Playbook source: `/Users/leon/ZCodeProject/fabv2-playbook` (not a Git repo).
- `finance-agent-v2`: <https://github.com/vals-ai/finance-agent-v2>, commit
  `b979786a8f9c49c178a88720ea4bb6fb16cbf818`, clean working tree.
- `model-library`: <https://github.com/vals-ai/model-library>, commit
  `b0cd8732c1ebc7cb901935b6aaf4b86c3d43d400` (`v0.1.29`), clean working tree.
- Oracle `answers.json` SHA-256:
  `bbf7ebc5100b467c07e21a0b8514f7bff760f98a72202c052d19279e1ee9b43a`.

Git history in this repository is the integrity record for all other archived
files.

