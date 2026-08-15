"""Schema for evolvable, machine-enforced FAB runtime policy."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ROOT_KEYS = {"schema_version", "filing_index", "search_page"}
_FILING_KEYS = {
    "enabled",
    "forms",
    "start_date",
    "end_date",
    "top_n_per_form",
    "max_tickers",
}
_SEARCH_KEYS = {"context_chars", "max_results_per_query", "max_calls_per_document"}
_FORMS = {"10-K", "10-Q", "8-K"}


def _exact_keys(payload: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(payload) - allowed
    if unknown:
        message = f"{label} contains unsupported keys: {sorted(unknown)}"
        raise ValueError(message)


def _bounded_int(payload: dict[str, Any], key: str, low: int, high: int, label: str) -> None:
    if key not in payload:
        return
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        message = f"{label}.{key} must be an integer in [{low}, {high}]"
        raise ValueError(message)


def parse_fab_policy(text: str) -> dict[str, Any]:
    """Parse and strictly validate every policy field the runtime can enforce."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        message = f"invalid JSON: {exc.msg} (line {exc.lineno})"
        raise ValueError(message) from exc
    if not isinstance(payload, dict):
        message = "runtime policy must be a JSON object"
        raise TypeError(message)
    _exact_keys(payload, _ROOT_KEYS, "runtime policy")
    if payload.get("schema_version") != 1:
        message = "runtime policy schema_version must equal 1"
        raise ValueError(message)

    filing = payload.get("filing_index")
    if filing is not None:
        if not isinstance(filing, dict):
            message = "filing_index must be an object"
            raise TypeError(message)
        _exact_keys(filing, _FILING_KEYS, "filing_index")
        if not isinstance(filing.get("enabled"), bool):
            message = "filing_index.enabled must be boolean"
            raise TypeError(message)
        forms = filing.get("forms")
        if not isinstance(forms, list) or not forms or any(form not in _FORMS for form in forms):
            message = f"filing_index.forms must be a non-empty subset of {sorted(_FORMS)}"
            raise ValueError(message)
        for key in ("start_date", "end_date"):
            if not isinstance(filing.get(key), str) or not _DATE.fullmatch(filing[key]):
                message = f"filing_index.{key} must use YYYY-MM-DD"
                raise ValueError(message)
        if filing["start_date"] > filing["end_date"]:
            message = "filing_index.start_date must not exceed end_date"
            raise ValueError(message)
        _bounded_int(filing, "top_n_per_form", 1, 10, "filing_index")
        _bounded_int(filing, "max_tickers", 1, 6, "filing_index")

    search = payload.get("search_page")
    if search is not None:
        if not isinstance(search, dict):
            message = "search_page must be an object"
            raise TypeError(message)
        _exact_keys(search, _SEARCH_KEYS, "search_page")
        _bounded_int(search, "context_chars", 100, 5_000, "search_page")
        _bounded_int(search, "max_results_per_query", 1, 100, "search_page")
        _bounded_int(search, "max_calls_per_document", 1, 20, "search_page")
        if not search:
            message = "search_page must declare at least one enforced limit"
            raise ValueError(message)
    return payload


def load_fab_policy(path: Path) -> dict[str, Any]:
    """Load a policy file through the same strict schema used by the guard."""
    return parse_fab_policy(path.read_text())
