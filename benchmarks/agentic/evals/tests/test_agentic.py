"""Deterministic verifiers for the 16 authored agentic tasks.

Each test copies the task directory into a sandbox, runs the real inner agent
once via agent_harness.run_task, then asserts on the files the agent produced.
Expected values are recomputed here from the task inputs by reference
implementations — never stored in the task dirs where the agent could read them.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import agent_harness
import pytest

TASKS_ROOT = Path(__file__).resolve().parents[2] / "tasks"


def read(sandbox: Path, name: str) -> str:
    path = sandbox / name
    assert path.exists(), f"expected output file /{name} was not created"
    return path.read_text()


def lines(sandbox: Path, name: str) -> list[str]:
    return [line.rstrip() for line in read(sandbox, name).strip().splitlines()]


# ---- reference implementations ------------------------------------------------


def verify_ex_invoice_total(task: Path, sandbox: Path) -> None:
    total = 0.0
    for path in sorted((task / "invoices").iterdir()):
        for row in path.read_text().strip().splitlines():
            _, qty, price = row.split(",")
            total += int(qty) * float(price)
    assert read(sandbox, "answer.txt").strip() == f"{total:.2f}"


def verify_ex_error_count(task: Path, sandbox: Path) -> None:
    count = sum(
        1
        for line in (task / "logs" / "app.log").read_text().splitlines()
        if line.startswith("ERROR") and "retry scheduled" not in line
    )
    assert read(sandbox, "answer.txt").strip() == str(count)


def verify_ex_top_customer(task: Path, sandbox: Path) -> None:
    totals: dict[str, float] = {}
    for row in (task / "orders.csv").read_text().strip().splitlines()[1:]:
        name, amount = row.split(",")
        totals[name] = totals.get(name, 0.0) + float(amount)
    best = max(totals.values())
    expected = sorted(name for name, value in totals.items() if value == best)[0]
    assert read(sandbox, "answer.txt").strip() == expected


def verify_ex_unique_domains(task: Path, sandbox: Path) -> None:
    domains = {
        line.rsplit("@", 1)[1].rstrip(">").lower()
        for line in (task / "contacts.txt").read_text().strip().splitlines()
    }
    assert read(sandbox, "answer.txt").strip() == str(len(domains))


def verify_fmt_json_report(task: Path, sandbox: Path) -> None:
    numbers = [int(line) for line in (task / "numbers.txt").read_text().split()]
    expected = {
        "count": len(numbers),
        "sum": sum(numbers),
        "mean": round(sum(numbers) / len(numbers), 2),
    }
    payload = json.loads(read(sandbox, "report.json"))
    assert payload == expected, f"report.json must be exactly {expected}, got {payload}"


def verify_fmt_sorted_csv(task: Path, sandbox: Path) -> None:
    rows = []
    for line in (task / "fruits.txt").read_text().split("\n"):
        if line.strip():
            name, qty = line.split()
            rows.append((name, int(qty)))
    rows.sort(key=lambda item: (-item[1], item[0]))
    expected = ["name,qty"] + [f"{name},{qty}" for name, qty in rows]
    assert lines(sandbox, "sorted.csv") == expected


def verify_fmt_fixed_width(task: Path, sandbox: Path) -> None:
    expected = []
    for line in (task / "items.txt").read_text().split("\n"):
        if line.strip():
            name, qty = line.split()
            expected.append(f"{name:<12}{qty:>5}")
    produced = [line for line in read(sandbox, "table.txt").split("\n") if line.strip()]
    assert produced == expected, f"expected exact fixed-width lines {expected!r}, got {produced!r}"


def verify_fmt_iso_dates(task: Path, sandbox: Path) -> None:
    expected = []
    for line in (task / "dates.txt").read_text().strip().splitlines():
        text = line.strip()
        for fmt in ("%B %d, %Y", "%m/%d/%Y", "%Y.%m.%d"):
            try:
                expected.append(datetime.strptime(text, fmt).strftime("%Y-%m-%d"))
                break
            except ValueError:
                continue
        else:  # pragma: no cover - authored data always parses
            msg = f"unparseable authored date: {text}"
            raise AssertionError(msg)
    assert lines(sandbox, "iso.txt") == expected


def verify_ms_even_pipeline(task: Path, sandbox: Path) -> None:
    numbers = [int(line) for line in (task / "raw.txt").read_text().split()]
    evens = sorted(value for value in numbers if value % 2 == 0)
    assert lines(sandbox, "evens.txt") == [str(value) for value in evens]
    assert read(sandbox, "answer.txt").strip() == str(sum(evens))


def verify_ms_word_reverse(task: Path, sandbox: Path) -> None:
    words = (task / "message.txt").read_text().split()
    expected = " ".join(word[::-1] for word in words)
    assert read(sandbox, "out.txt").strip() == expected


def verify_ms_rename_plan(task: Path, sandbox: Path) -> None:
    files = sorted(
        (task / "data").iterdir(),
        key=lambda path: (path.stat().st_size, path.name),
    )
    expected = [
        f"{path.name} -> {index:02d}_{path.name}" for index, path in enumerate(files, start=1)
    ]
    assert lines(sandbox, "plan.txt") == expected


def verify_ms_checksum(task: Path, sandbox: Path) -> None:
    total = 0
    for path in (task / "data").iterdir():
        line_count = len(path.read_text().splitlines())
        total += line_count * len(path.name)
    assert read(sandbox, "answer.txt").strip() == str(total)


def verify_rb_distractor(task: Path, sandbox: Path) -> None:
    total = sum(
        int(row.split(",")[1])
        for row in (task / "data.csv").read_text().strip().splitlines()[1:]
    )
    answer = read(sandbox, "answer.txt").strip()
    assert answer != "42", "the hint file's shortcut answer was trusted instead of the data"
    assert answer == str(total)


def verify_rb_empty_edge(task: Path, sandbox: Path) -> None:
    total = 0
    for path in (task / "sales").iterdir():
        for line in path.read_text().splitlines():
            if line.strip():
                total += int(line.split(",")[1])
    assert read(sandbox, "answer.txt").strip() == str(total)


def verify_rb_one_line(task: Path, sandbox: Path) -> None:
    expected = str(len((task / "story.txt").read_text().split()))
    content = read(sandbox, "answer.txt")
    stripped = content.strip()
    assert "\n" not in stripped, "answer.txt must contain exactly one line"
    assert stripped == expected


def verify_rb_messy_names(task: Path, sandbox: Path) -> None:
    names = sorted(
        {
            line.strip().lower()
            for line in (task / "names.txt").read_text().splitlines()
            if line.strip()
        }
    )
    assert lines(sandbox, "clean.txt") == names


VERIFIERS = {
    "ex-invoice-total": verify_ex_invoice_total,
    "ex-error-count": verify_ex_error_count,
    "ex-top-customer": verify_ex_top_customer,
    "ex-unique-domains": verify_ex_unique_domains,
    "fmt-json-report": verify_fmt_json_report,
    "fmt-sorted-csv": verify_fmt_sorted_csv,
    "fmt-fixed-width": verify_fmt_fixed_width,
    "fmt-iso-dates": verify_fmt_iso_dates,
    "ms-even-pipeline": verify_ms_even_pipeline,
    "ms-word-reverse": verify_ms_word_reverse,
    "ms-rename-plan": verify_ms_rename_plan,
    "ms-checksum": verify_ms_checksum,
    "rb-distractor": verify_rb_distractor,
    "rb-empty-edge": verify_rb_empty_edge,
    "rb-one-line": verify_rb_one_line,
    "rb-messy-names": verify_rb_messy_names,
}


@pytest.mark.timeout(420)
@pytest.mark.parametrize("task_id", sorted(VERIFIERS))
def test_task(task_id: str, model: str, tmp_path: Path, record_tokens) -> None:
    task = TASKS_ROOT / task_id
    assert task.exists(), f"task fixture missing: {task}"
    sandbox = tmp_path / task_id
    shutil.copytree(task, sandbox)

    usage = agent_harness.run_task(task_root=str(sandbox), model=model)
    record_tokens(usage.get("total_tokens", 0))

    VERIFIERS[task_id](task, sandbox)
