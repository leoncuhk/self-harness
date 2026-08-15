from self_harness.fabv2_leaderboard import (
    DATASET_SHA256,
    PROTOCOL_ID,
    render_markdown,
    summarize_submission,
)


def _submission(*, submission_id="candidate", judge="numeric-diagnostic", repeats=3, track="open-harness"):
    metric = "partial_credit" if judge == "official" else "ungated_credit"
    runs = []
    for seed in range(repeats):
        runs.append(
            {
                "seed": seed,
                "outcomes": [
                    {
                        "qid": f"q{index:03d}",
                        "status": "measured",
                        "metrics": {metric: index / 27, "all_pass": index == 27},
                        "tokens": 100,
                    }
                    for index in range(1, 28)
                ],
            }
        )
    return {
        "submission_id": submission_id,
        "protocol_id": PROTOCOL_ID,
        "dataset_sha256": DATASET_SHA256,
        "track": track,
        "model": "provider/model-version",
        "harness": "abc123",
        "judge": judge,
        "apparatus": "free-reproduction-v1",
        "contamination": "public-rubric-aware",
        "search": {"tokens": 1234},
        "runs": runs,
    }


def test_complete_three_repeat_submission_is_rankable():
    row = summarize_submission(_submission())

    assert row.eligible
    assert row.repeats == 3
    assert row.score == 14 / 27
    assert row.ci_low < row.score < row.ci_high
    assert row.eval_tokens == 8_100
    assert row.search_tokens == 1_234


def test_oracle_and_single_repeat_are_excluded():
    row = summarize_submission(_submission(repeats=1, track="oracle"))

    assert not row.eligible
    assert "oracle track" in row.ineligible_reason
    assert "fewer than three" in row.ineligible_reason


def test_official_and_diagnostic_evidence_render_in_separate_tables():
    diagnostic = summarize_submission(_submission(submission_id="diagnostic"))
    official = summarize_submission(_submission(submission_id="official", judge="official"))

    output = render_markdown([diagnostic, official])

    assert "Official-judge evidence" in output
    assert "Local numeric diagnostic" in output
    assert output.count("`official`") == 1
    assert output.count("`diagnostic`") == 1
