import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _telemetry_module():
    path = ROOT / "benchmarks" / "fabv2" / "evals" / "frozen" / "telemetry.py"
    spec = importlib.util.spec_from_file_location("fabv2_frozen_telemetry", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_behavior_metrics_preserve_diagnostic_signals_without_reward_shaping():
    telemetry = _telemetry_module()
    metrics = telemetry.behavior_metrics(
        {
            "turns": 10,
            "error_count": 2,
            "tool_calls_count": 8,
            "recovery_used": True,
            "recovery_turns": 1,
            "recovery_tokens": 1200,
            "tool_usage": {
                "edgar_search": 2,
                "fetch_page_text": 1,
                "calculator": 4,
                "submit_final_result": 1,
            },
        }
    )

    assert metrics["agent_error_count"] == 2
    assert metrics["errors_per_turn"] == 0.2
    assert metrics["tool_call_count"] == 8
    assert metrics["edgar_search_count"] == 2
    assert metrics["fetch_page_text_count"] == 1
    assert metrics["calculator_count"] == 4
    assert metrics["submission_rate"] == 1
    assert metrics["recovery_rate"] == 1
    assert metrics["recovery_turns"] == 1
    assert metrics["recovery_tokens"] == 1200


def test_behavior_metrics_fall_back_to_usage_counts():
    telemetry = _telemetry_module()
    metrics = telemetry.behavior_metrics(
        {"turns": 0, "tool_usage": {"fetch_page_text": 3}}
    )

    assert metrics["tool_call_count"] == 3
    assert metrics["errors_per_turn"] == 0
    assert metrics["submission_rate"] == 0
    assert metrics["recovery_rate"] == 0
