# FAB v2 case study

This directory contains all 27 questions and rubrics in the official FAB v2
public development set, a frozen deterministic numeric diagnostic, and a
free-tool reproduction of the competition agent interface. Source provenance,
license, counts, and the pinned SHA-256 are recorded in `data/manifest.json` and
`THIRD_PARTY_NOTICES.md`.

The public rubrics are development data. After using them for diagnosis or
prompt design, none of these 27 questions is an untouched test. The local judge
does not implement Vals' qualitative judge and the free tools are not identical
to the paid official apparatus, so local numbers must never be presented as
official FAB leaderboard results.

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

The executed case study still uses three selected cases and one repeat; expanding
the vendored data does not retroactively strengthen that evidence. Three cases
and one repeat are not enough for a competition-wide efficacy claim.
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
for a question. `configs/fabv2_self_harness_v2.toml` exposed ungated weighted
credit and true numeric-criterion recall without changing the dealbreaker score,
but its executed eight-turn calibration still produced empty answers and no
gain. See `docs/fabv2-v2-calibration.md`; v3 is the unexecuted 14-turn successor.

Regenerate and verify the public artifacts with:

```bash
python benchmarks/fabv2/tools/build_public_data.py --check
```
