"""Cost and behavior accounting shared by FAB agent execution phases."""

from __future__ import annotations

from better_harness.usage import total_tokens


def result_tokens(result) -> int | None:
    """Return billed tokens for one agent phase, including compaction."""
    if result is None:
        return None
    aggregate = total_tokens(getattr(result, "final_aggregated_metadata", None))
    compaction = total_tokens(getattr(result, "final_compaction_metadata", None))
    if aggregate is None and compaction is None:
        return None
    return (aggregate or 0) + (compaction or 0)


def merge_tool_usage(*results) -> dict[str, int]:
    """Merge tool counters from the main and recovery phases."""
    merged: dict[str, int] = {}
    for result in results:
        usage = getattr(result, "tool_usage", None)
        if not isinstance(usage, dict):
            continue
        for name, count in usage.items():
            if isinstance(count, (int, float)) and not isinstance(count, bool):
                merged[str(name)] = merged.get(str(name), 0) + int(count)
    return merged
