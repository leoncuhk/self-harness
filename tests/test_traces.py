from __future__ import annotations

import json
from pathlib import Path

from self_harness.core import CaseOutcome
from self_harness.traces import (
    compact_failure_message,
    normalize_outcome,
    trace_text,
    write_experience_bundle,
)


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
    (tmp_path / "judge.json").write_text(
        json.dumps(
            {
                "partial_credit": 0.25,
                "ungated_credit": 0.5,
                "failed_numeric": ["missing CAGR"],
                "private_debug": "must not be copied",
            }
        )
    )
    research_dir = tmp_path / "trajectory" / "prime_workspace"
    research_dir.mkdir(parents=True)
    (research_dir / "research_trace.json").write_text('[{"error":"SEC HTTP 503"}]\n')
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
    assert record.verifier == {
        "partial_credit": 0.25,
        "ungated_credit": 0.5,
        "failed_numeric": ["missing CAGR"],
    }
    assert record.research_tail == '[{"error":"SEC HTTP 503"}]'
    assert record.diagnostic_facets == (
        "budget_boundary",
        "data_plane_access",
        "numeric_verifier_miss",
        "submission_not_observed",
    )
    assert "web_search" in trace_text(outcome)
    assert "sec http 503" in trace_text(outcome)


def test_finance_diagnostic_facets_route_cross_layer_failure(tmp_path: Path):
    (tmp_path / "run.json").write_text(
        json.dumps(
            {
                "stop_reason": "compiled_after_max_tokens",
                "tool_usage": {"submit_final_result": 1},
            }
        )
    )
    (tmp_path / "judge.json").write_text(
        json.dumps({"failed_numeric": ["FY2026 Adjusted EBITDA is $14,745"]})
    )
    research_dir = tmp_path / "trajectory" / "prime_workspace"
    research_dir.mkdir(parents=True)
    (research_dir / "research_trace.json").write_text(
        "Actual source period differs from guidance projection; resolve Exhibit 99.1 through "
        "index.json, then reconcile D&A, SBC, NWC, CapEx, and FCFF component calculation."
    )
    outcome = CaseOutcome(
        case_id="q",
        split="train",
        stratum="financial-modeling",
        status="failed",
        score=0.0,
        duration_s=1.0,
        failure_message="assertion failed",
        artifacts_dir=str(tmp_path),
    )

    assert normalize_outcome(outcome).diagnostic_facets == (
        "answer_materialization",
        "budget_boundary",
        "cash_flow_reconciliation",
        "filing_attachment_resolution",
        "forecast_period_provenance",
        "numeric_verifier_miss",
    )


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


def test_compact_failure_message_prefers_pytest_error_lines():
    message = """qid = 'q004'
def test_question():
    record_usage = <function fixture>
E   assert 0.125 >= 1.0
E   fabv2:q004 partial=0.125 turns=14
"""

    compact = compact_failure_message(message)

    assert compact == "E   assert 0.125 >= 1.0\nE   fabv2:q004 partial=0.125 turns=14"
    assert "record_usage" not in compact
