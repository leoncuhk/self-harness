"""Deterministic verifiers for the 16 authored agentic tasks (difficulty rev 1).

Each test copies the task directory into a sandbox, runs the real inner agent
once via agent_harness.run_task, then asserts on the files the agent produced.
Expected values are recomputed here from the task inputs by reference
implementations — never stored in the task dirs where the agent could read them.
"""

from __future__ import annotations

import csv
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
    grand = 0.0
    for path in sorted((task / "invoices").iterdir()):
        subtotal = 0.0
        discount = 0.0
        for row in csv.reader(path.read_text().strip().splitlines()):
            if row[0] == "DISCOUNT":
                discount = float(row[1])
            else:
                subtotal += int(row[1]) * float(row[2])
        grand += subtotal * (1 - discount / 100)
    assert read(sandbox, "answer.txt").strip() == f"{grand:.2f}"


def verify_ex_error_count(task: Path, sandbox: Path) -> None:
    errors = 0
    warnings = 0
    for line in (task / "logs" / "app.log").read_text().splitlines():
        parts = line.split(maxsplit=2)
        level, message = parts[1], parts[2]
        if level == "ERROR" and "retry scheduled" not in message:
            errors += 1
        if level == "WARN" and "disk" in message:
            warnings += 1
    assert read(sandbox, "answer.txt").strip() == f"errors={errors};warnings={warnings}"


def verify_ex_top_customer(task: Path, sandbox: Path) -> None:
    totals: dict[str, float] = {}
    for name, amount in csv.reader((task / "orders.csv").read_text().strip().splitlines()[1:]):
        value = amount.strip()
        negative = value.startswith("(") and value.endswith(")")
        value = value.strip("()").lstrip("$")
        parsed = float(value) * (-1 if negative else 1)
        key = name.strip().lower()
        totals[key] = totals.get(key, 0.0) + parsed
    best = max(totals.values())
    winner = sorted(name for name, total in totals.items() if total == best)[0]
    assert read(sandbox, "answer.txt").strip() == f"{winner}:{best:.2f}"


def verify_ex_unique_domains(task: Path, sandbox: Path) -> None:
    domains = set()
    for line in (task / "contacts.txt").read_text().splitlines():
        if "<" not in line or "@" not in line:
            continue
        email = line.rsplit("<", 1)[1].rstrip(">").strip()
        if "@" not in email:
            continue
        domain = email.rsplit("@", 1)[1].lower()
        domain = domain.removeprefix("www.")
        domains.add(domain)
    assert read(sandbox, "answer.txt").strip() == str(len(domains))


def verify_fmt_json_report(task: Path, sandbox: Path) -> None:
    numbers = sorted(int(line) for line in (task / "numbers.txt").read_text().split())
    count = len(numbers)
    middle = count // 2
    median = numbers[middle] if count % 2 else (numbers[middle - 1] + numbers[middle]) / 2
    expected = {
        "count": count,
        "sum": sum(numbers),
        "mean": round(sum(numbers) / count, 2),
        "median": round(median, 2),
        "range": max(numbers) - min(numbers),
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
    expected = ["name,qty"]
    expected += [f"{name},{qty}" for name, qty in rows]
    expected += [f"TOTAL,{sum(qty for _, qty in rows)}"]
    assert lines(sandbox, "sorted.csv") == expected


def verify_fmt_fixed_width(task: Path, sandbox: Path) -> None:
    expected = []
    for line in (task / "items.txt").read_text().split("\n"):
        if line.strip():
            name, qty, price = line.split()
            expected.append(f"{name:<12}{qty:>5}{float(price):>9.2f}")
    produced = [line for line in read(sandbox, "table.txt").split("\n") if line.strip()]
    assert produced == expected, f"expected exact fixed-width lines {expected!r}, got {produced!r}"


def verify_fmt_iso_dates(task: Path, sandbox: Path) -> None:
    expected = []
    for line in (task / "dates.txt").read_text().strip().splitlines():
        text = line.strip()
        for fmt in ("%B %d, %Y", "%m/%d/%Y", "%Y.%m.%d", "%d-%b-%y", "%Y-%j"):
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
    squares = [value * value for value in evens]
    cumsum = []
    running = 0
    for square in squares:
        running += square
        cumsum.append(running)
    assert lines(sandbox, "evens.txt") == [str(value) for value in evens]
    assert lines(sandbox, "squares.txt") == [str(value) for value in squares]
    assert lines(sandbox, "cumsum.txt") == [str(value) for value in cumsum]
    assert read(sandbox, "answer.txt").strip() == str(running)


def verify_ms_word_reverse(task: Path, sandbox: Path) -> None:
    def transform(word: str) -> str:
        if len(word) <= 3:
            return word
        reversed_word = word[::-1].lower()
        if word[0].isupper():
            return reversed_word[0].upper() + reversed_word[1:]
        return reversed_word

    words = (task / "message.txt").read_text().split()
    expected = " ".join(transform(word) for word in words)
    assert read(sandbox, "out.txt").strip() == expected


def verify_ms_rename_plan(task: Path, sandbox: Path) -> None:
    def sort_key(path: Path) -> tuple:
        line_count = len(path.read_text().splitlines())
        return (-line_count, path.stat().st_size, path.name)

    files = sorted((task / "data").iterdir(), key=sort_key)
    expected = [
        f"{path.name} -> {index:02d}_{path.name}" for index, path in enumerate(files, start=1)
    ]
    expected.append(f"total_files={len(files)}")
    assert lines(sandbox, "plan.txt") == expected


def verify_ms_checksum(task: Path, sandbox: Path) -> None:
    total = 0
    for path in (task / "data").iterdir():
        if path.name.endswith((".txt", ".md")):
            total += len(path.read_text().splitlines()) * len(path.name)
        else:
            total += path.stat().st_size % 7
    assert read(sandbox, "answer.txt").strip() == str(total)


def verify_rb_distractor(task: Path, sandbox: Path) -> None:
    rows = (task / "data.csv").read_text().strip().splitlines()[1:]
    amount_total = sum(int(row.split(",")[2]) for row in rows)
    quantity_total = sum(int(row.split(",")[1]) for row in rows)
    answer = read(sandbox, "answer.txt").strip()
    assert answer != str(quantity_total), (
        "the hint file's wrong-column shortcut was trusted instead of the amount column"
    )
    assert answer == str(amount_total)


def verify_rb_empty_edge(task: Path, sandbox: Path) -> None:
    total = 0
    for path in (task / "sales").iterdir():
        for line in path.read_text().splitlines():
            text = line.strip()
            if not text or text == "region,amount":
                continue
            total += int(text.split(",")[1])
    assert read(sandbox, "answer.txt").strip() == str(total)


def verify_rb_one_line(task: Path, sandbox: Path) -> None:
    tokens = (task / "story.txt").read_text().split()
    expected = str(sum(1 for token in tokens if any(ch.isalnum() for ch in token)))
    content = read(sandbox, "answer.txt")
    stripped = content.strip()
    assert "\n" not in stripped, "answer.txt must contain exactly one line"
    assert stripped == expected


def verify_rb_messy_names(task: Path, sandbox: Path) -> None:
    names = set()
    for line in (task / "names.txt").read_text().splitlines():
        text = line.replace("\u00a0", " ").replace("\t", " ")
        text = " ".join(text.split())
        if text:
            names.add(text.lower())
    assert lines(sandbox, "clean.txt") == sorted(names)


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
