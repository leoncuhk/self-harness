from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[2] / "workspace"
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frozen"))

COUNTS = {"passed": 0, "failed": 0, "skipped": 0}
TOKENS = {"total": 0}
FINGERPRINTS: set[str] = set()
METRICS: dict[str, float] = {}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--model", action="store", default="openai/deepseek-v4-flash")
    parser.addoption("--evals-report-file", action="store", default="")


@pytest.fixture
def model(pytestconfig: pytest.Config) -> str:
    return str(pytestconfig.getoption("--model"))


@pytest.fixture
def record_usage():
    def _record(usage: dict) -> None:
        TOKENS["total"] += int(usage.get("total_tokens", 0))
        FINGERPRINTS.update(usage.get("system_fingerprints", []))

    return _record


@pytest.fixture
def record_metrics():
    def _record(metrics: dict[str, float]) -> None:
        METRICS.update({str(key): float(value) for key, value in metrics.items()})

    return _record


def pytest_configure(config: pytest.Config) -> None:
    del config
    for key in COUNTS:
        COUNTS[key] = 0
    TOKENS["total"] = 0
    FINGERPRINTS.clear()
    METRICS.clear()


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when != "call":
        return
    if report.passed:
        COUNTS["passed"] += 1
    elif report.failed:
        COUNTS["failed"] += 1
    elif report.skipped:
        COUNTS["skipped"] += 1


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    del exitstatus
    summary_file = str(session.config.getoption("--evals-report-file"))
    if not summary_file:
        return
    total = COUNTS["passed"] + COUNTS["failed"] + COUNTS["skipped"]
    payload = {
        "created_at": "fabv2",
        "sdk_version": "fabv2",
        "model": str(session.config.getoption("--model")),
        "passed": COUNTS["passed"],
        "failed": COUNTS["failed"],
        "skipped": COUNTS["skipped"],
        "total": total,
        "correctness": 0.0 if total == 0 else COUNTS["passed"] / total,
        "total_tokens": TOKENS["total"],
        "system_fingerprints": sorted(FINGERPRINTS),
        "score": METRICS.get("partial_credit", 0.0),
        "metrics": dict(METRICS),
    }
    path = Path(summary_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
