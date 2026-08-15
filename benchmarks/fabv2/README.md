# FAB v2 case study

This directory contains the six supplied FAB v2 finance-research questions, a
frozen deterministic numeric evaluator, and a free-tool reproduction of the
competition agent interface.

The self-harness case study exposes four real runtime surfaces:

- `prompt.txt` — stable identity and tool contract;
- `research_policy.md` — planning, retrieval, and source selection;
- `verification_policy.md` — arithmetic and completeness checks;
- `submission_policy.md` — final artifact requirements.

`configs/fabv2_self_harness.toml` uses the official dealbreaker-gated partial
credit as its objective while retaining binary pass rate as a non-regression constraint. Its
bounded case study uses one calculation-heavy train case, one validation case,
and one locked-test case under an identical eight-turn budget. The separate B5
config runs the hand-engineered prompt on the same cases and budget.

Three selected cases and one repeat are not enough for a competition-wide efficacy claim.
The experiment verifies integration and provides a falsifiable local result;
the report must disclose its wide uncertainty and compare against both B0 and
the hand-engineered B5 prompt.

The executed bounded result is recorded in
[`docs/fabv2-case-study.md`](../../docs/fabv2-case-study.md). In the first frozen
run, the autonomous candidate was correctly rejected and no arm improved the
primary objective; this is evidence of integration and conservative selection,
not evidence of FAB performance gain.

That run also falsified the assumption that the old `numeric_recall` diagnostic
measured answer quality: it was rubric numeric coverage and therefore constant
for a question. `configs/fabv2_self_harness_v2.toml` is an unexecuted successor
that exposes ungated weighted credit and true numeric-criterion recall without
changing the official dealbreaker score.
