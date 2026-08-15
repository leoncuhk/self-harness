"""Frozen conversion of FAB agent behavior into numeric diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

TRACKED_TOOLS = (
    "edgar_search",
    "fetch_page_text",
    "calculator",
    "price_history",
    "ipython",
    "submit_final_result",
)


def _count(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, float(value))


def behavior_metrics(out: Mapping[str, Any]) -> dict[str, float]:
    """Return descriptive metrics without converting correlation into reward."""
    raw_usage = out.get("tool_usage")
    usage = raw_usage if isinstance(raw_usage, Mapping) else {}
    tool_counts = {name: _count(usage.get(name)) for name in TRACKED_TOOLS}

    reported_calls = _count(out.get("tool_calls_count"))
    total_calls = reported_calls or sum(_count(value) for value in usage.values())
    errors = _count(out.get("error_count"))
    turns = _count(out.get("turns"))

    metrics = {
        "agent_error_count": errors,
        "errors_per_turn": errors / max(turns, 1.0),
        "tool_call_count": total_calls,
        "submission_rate": float(tool_counts["submit_final_result"] > 0),
        "recovery_rate": float(bool(out.get("recovery_used", False))),
        "recovery_turns": _count(out.get("recovery_turns")),
        "recovery_tokens": _count(out.get("recovery_tokens")),
    }
    metrics.update({f"{name}_count": count for name, count in tool_counts.items()})
    return metrics
