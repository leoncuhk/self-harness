from __future__ import annotations

import json
from pathlib import Path

from better_harness.core import CaseOutcome
from better_harness.traces import normalize_outcome, trace_text, write_experience_bundle


def test_normalize_outcome_reads_runner_artifacts(tmp_path: Path):
    (tmp_path / "run.json").write_text(
        json.dumps(
            {
                "stop_reason": "turn_limit",
                "turns": 14,
                "tokens": 9000,
                "tool_usage": {"web_search": 4},
            }
        )
    )
    (tmp_path / "trace.jsonl").write_text('{"event":"ci_end","returncode":1}\n')
    outcome = CaseOutcome(
        case_id="case",
        split="train",
        stratum="s",
        status="failed",
        score=0.4,
        duration_s=1.0,
        failure_message="assertion failed",
        artifacts_dir=str(tmp_path),
    )
    record = normalize_outcome(outcome)
    assert record.stop_reason == "turn_limit"
    assert record.tool_usage == {"web_search": 4}
    assert record.events[0]["returncode"] == 1
    assert "web_search" in trace_text(outcome)


def test_experience_bundle_is_bounded_and_jsonl(tmp_path: Path):
    outcomes = [
        CaseOutcome(
            case_id=f"case-{index}",
            split="train",
            stratum="s",
            status="failed",
            score=0.0,
            duration_s=1.0,
        )
        for index in range(4)
    ]
    records = write_experience_bundle(tmp_path / "experience", outcomes, max_cases=2)
    assert len(records) == 2
    lines = (tmp_path / "experience" / "records.jsonl").read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["case_id"] == "case-0"
