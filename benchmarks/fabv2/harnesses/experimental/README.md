# Experimental FAB harnesses

These profiles are reproducible research artifacts, not promoted defaults.

`forecast-provenance-v1` is the frozen q025 candidate produced by the diagnostic micro-evolution
documented in `docs/evaluation/fabv2-case-study.md`. It passed q025 in 3/3 independent GPT-5.6-sol
+ Codex repeats, but regressed q013 in the one-repeat control set. The conservative global gate
therefore rejected promotion; `harnesses/strong` remains the active default.
