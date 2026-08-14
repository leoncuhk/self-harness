"""Normalize provider-specific token metadata without treating missing data as zero."""

from __future__ import annotations

from collections.abc import Mapping


def _number(metadata: object, key: str) -> float | None:
    value = metadata.get(key) if isinstance(metadata, Mapping) else getattr(metadata, key, None)
    if isinstance(value, int | float):
        return float(value)
    return None


def total_tokens(metadata: object | None) -> int | None:
    """Return a total from common aggregate shapes, or ``None`` when absent.

    Some model libraries expose ``total_tokens`` while others expose the
    non-overlapping ``total_input_tokens`` and ``total_output_tokens`` fields.
    Cache and reasoning counts are already included in those aggregate fields
    and must not be added a second time.
    """
    if metadata is None:
        return None
    if (combined := _number(metadata, "total_tokens")) is not None:
        return int(combined)
    input_tokens = _number(metadata, "total_input_tokens")
    output_tokens = _number(metadata, "total_output_tokens")
    if input_tokens is None and output_tokens is None:
        return None
    return int((input_tokens or 0.0) + (output_tokens or 0.0))
