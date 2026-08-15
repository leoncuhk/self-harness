import json
from pathlib import Path

import pytest
from compare_fabv2_v5 import render


def _split(value: float, *, fingerprint: str = "frozen") -> dict:
    return {
        "metrics": {"ungated_credit": value},
        "correctness": value,
        "evaluation_fingerprint": fingerprint,
    }


def _write_run(
    root: Path,
    *,
    baseline: tuple[float, float, float],
    final: tuple[float, float, float],
    fingerprint: str = "frozen",
) -> None:
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps({"goal": {"primary_metric": "ungated_credit"}})
    )
    payload = {}
    for stage, values in (("baseline", baseline), ("final", final)):
        for split, value in zip(("train", "holdout", "scorecard"), values, strict=True):
            payload[f"{stage}_{split}"] = _split(value, fingerprint=fingerprint)
    (root / "report.json").write_text(json.dumps(payload))


def test_v5_report_compares_seed_hand_harness_and_final(tmp_path: Path):
    evolved = tmp_path / "evolved"
    b5 = tmp_path / "b5"
    _write_run(evolved, baseline=(0.2, 0.2, 0.2), final=(0.5, 0.4, 0.45))
    _write_run(b5, baseline=(0.3, 0.3, 0.4), final=(0.3, 0.3, 0.4))

    output = render(evolved_run=evolved, b5_run=b5)

    assert "Self-Harness validation delta over B0: `+0.2000`" in output
    assert "Self-Harness beats B5 on locked scorecard: `yes`" in output
    assert "Equal-total-compute retry/Best-of-N" in output


def test_v5_report_rejects_mixed_evaluation_contracts(tmp_path: Path):
    evolved = tmp_path / "evolved"
    b5 = tmp_path / "b5"
    _write_run(evolved, baseline=(0.2, 0.2, 0.2), final=(0.3, 0.3, 0.3))
    _write_run(
        b5,
        baseline=(0.2, 0.2, 0.2),
        final=(0.2, 0.2, 0.2),
        fingerprint="different",
    )

    with pytest.raises(ValueError, match="frozen evaluation fingerprint"):
        render(evolved_run=evolved, b5_run=b5)


def test_v5_report_labels_retry_selection_as_oracle(tmp_path: Path):
    evolved = tmp_path / "evolved"
    b5 = tmp_path / "b5"
    retry = tmp_path / "retry"
    _write_run(evolved, baseline=(0.2, 0.2, 0.2), final=(0.3, 0.3, 0.3))
    _write_run(b5, baseline=(0.2, 0.2, 0.2), final=(0.2, 0.2, 0.2))
    for split, qid in (("train", "q004"), ("holdout", "q005"), ("scorecard", "q006")):
        for repeat, value in enumerate((0.1, 0.8)):
            case = (
                retry
                / "history"
                / ("visible" if split == "train" else "private")
                / split
                / "baseline"
                / f"rep{repeat:02d}"
                / "cases"
                / qid
            )
            case.mkdir(parents=True)
            (case / "judge.json").write_text(
                json.dumps(
                    {
                        "qid": qid,
                        "ungated_credit": value,
                        "partial_credit": value,
                    }
                )
            )

    output = render(evolved_run=evolved, b5_run=b5, retry_run=retry)

    assert "B0 retries per question: `2`" in output
    assert "Oracle best-of-N `ungated_credit`: `0.8000`" in output
    assert "oracle upper bound" in output
