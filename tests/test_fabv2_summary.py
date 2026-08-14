from scripts.summarize_fabv2_case_study import render


def _split(score, passed):
    return {"score": score, "passed": passed, "total": 1, "outcomes": []}


def _report(*, baseline_scores, final_scores, changed=()):
    return {
        "baseline": {"changed_surfaces": []},
        "final": {"changed_surfaces": list(changed)},
        "baseline_train": _split(baseline_scores[0], 0),
        "baseline_holdout": _split(baseline_scores[1], 0),
        "baseline_scorecard": _split(baseline_scores[2], 0),
        "final_train": _split(final_scores[0], 1),
        "final_holdout": _split(final_scores[1], 1),
        "final_scorecard": _split(final_scores[2], 1),
    }


def test_fabv2_summary_reports_deltas_and_limitations():
    evolved = _report(
        baseline_scores=(0.1, 0.2, 0.3),
        final_scores=(0.8, 0.7, 0.6),
        changed=("research_policy",),
    )
    comparator = _report(baseline_scores=(0.4, 0.5, 0.5), final_scores=(0.4, 0.5, 0.5))

    output = render(evolved, comparator)

    assert "Self-Harness final" in output
    assert "research_policy" in output
    assert "Validation score delta (final - seed): +0.500" in output
    assert "Locked-test score delta (final - seed): +0.300" in output
    assert "n=1 per split" in output
