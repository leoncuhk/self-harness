"""Build reproducible FAB v2 public-question artifacts from the official CSV.

The CSV and rubric text are public development data. The generated rubric file
belongs only to the frozen evaluator; outer-loop proposals must never receive it.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "public.csv"
QUESTIONS_PATH = ROOT / "questions.json"
RUBRICS_PATH = ROOT / "evals" / "frozen" / "rubrics.json"
MANIFEST_PATH = ROOT / "data" / "manifest.json"

SOURCE_REPOSITORY = "https://github.com/vals-ai/finance-agent-v2"
SOURCE_COMMIT = "b979786a8f9c49c178a88720ea4bb6fb16cbf818"
EXPECTED_CSV_SHA256 = "27b48c08a6099bc076b4194cac7cefe295082b9aedcbc67f4fedfa70468b427e"

NUM_RE = re.compile(
    r"(?<![\d.,])(?P<neg>[-(]?)\$?(?P<num>\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s?"
    r"(?P<unit>%|bps|basis points|x)?\)?(?!\d)",
)


def _looks_like_year(text: str, match: re.Match[str]) -> bool:
    """Reject dates, fiscal-year labels, and bare year anchors."""
    number = match.group("num")
    if "," in number or "." in number:
        return False
    value = int(number)
    before = text[: match.start()]
    after = text[match.end() :]
    if re.search(r"[-/.,]\s*$", before) or re.match(r"^[-/.,]\s?\d", after):
        return True
    if re.match(r"^A\b", after):
        return True
    if re.search(r"FY\s*$", before, re.IGNORECASE):
        return True
    return 1900 <= value <= 2035


def extract_anchors(text: str) -> list[dict[str, float | str]]:
    """Extract answer anchors for the deterministic diagnostic track."""
    anchors: list[dict[str, float | str]] = []
    for match in NUM_RE.finditer(text):
        raw = match.group(0)
        unit_raw = (match.group("unit") or "").strip()
        value = float(match.group("num").replace(",", ""))
        if _looks_like_year(text, match):
            continue
        scale_match = re.search(
            r"(million|billion|thousand)",
            text[match.end() : match.end() + 22],
            re.IGNORECASE,
        )
        # Bare small integers are usually list indices or counts, but a currency
        # amount such as "$4.06 billion" is a high-value numeric anchor. The old
        # ordering discarded it before looking for the scale suffix and removed
        # half of q005 from the optimization signal.
        if (
            unit_raw == ""
            and not match.group("neg")
            and "$" not in raw
            and scale_match is None
            and 0 <= value <= 9
        ):
            continue
        before = text[max(0, match.start() - 14) : match.start()].lower()
        if (
            bool(match.group("neg"))
            or raw.strip().startswith("(")
            or re.search(r"negative\s*\$?$|reduction\s+of\s+\$?$", before)
        ):
            value = -value
        unit = {
            "%": "percent",
            "bps": "bps",
            "basis points": "bps",
            "x": "multiple",
            "": "plain",
        }[unit_raw]
        anchors.append(
            {
                "value": value,
                "unit": unit,
                "scale": "" if scale_match is None else scale_match.group(1).lower(),
                "raw": raw.strip(),
            }
        )
    return anchors


def build(csv_path: Path = CSV_PATH) -> tuple[dict[str, str], list[dict]]:
    """Parse the source into stable question and evaluator artifacts."""
    rows = list(csv.DictReader(csv_path.open()))
    questions: dict[str, str] = {}
    rubrics: list[dict] = []
    for index, row in enumerate(rows, 1):
        qid = f"q{index:03d}"
        question = row["Question"].replace("\n", " ")
        criteria = []
        for criterion in json.loads(row["Rubric"]):
            text = criterion["criteria"]
            criteria.append(
                {
                    "text": text,
                    "severity": criterion["modifiers"]["severity"],
                    "must_pass": criterion["modifiers"].get("category") == "must_pass",
                    "numeric": extract_anchors(text),
                }
            )
        questions[qid] = question
        rubrics.append(
            {
                "id": qid,
                "question": question,
                "category": row["Question Type"],
                "expert_mins": int(row["Expert time (mins)"]),
                "criteria": criteria,
            }
        )
    return questions, rubrics


def _render(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _manifest(csv_path: Path, rubrics: list[dict]) -> dict:
    categories: dict[str, int] = {}
    for question in rubrics:
        categories[question["category"]] = categories.get(question["category"], 0) + 1
    return {
        "benchmark": "Finance Agent Benchmark v2 public development set",
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": SOURCE_COMMIT,
        "source_file": "data/public.csv",
        "source_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "license": "MIT; see THIRD_PARTY_NOTICES.md",
        "evaluation_status": "public-development-only",
        "question_count": len(rubrics),
        "criterion_count": sum(len(item["criteria"]) for item in rubrics),
        "must_pass_count": sum(
            criterion["must_pass"] for item in rubrics for criterion in item["criteria"]
        ),
        "numeric_criterion_count": sum(
            bool(criterion["numeric"])
            for item in rubrics
            for criterion in item["criteria"]
        ),
        "categories": dict(sorted(categories.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated files drift")
    args = parser.parse_args()
    actual_hash = hashlib.sha256(CSV_PATH.read_bytes()).hexdigest()
    if actual_hash != EXPECTED_CSV_SHA256:
        raise SystemExit(
            f"source CSV hash drifted: expected {EXPECTED_CSV_SHA256}, got {actual_hash}"
        )
    questions, rubrics = build()
    outputs = {
        QUESTIONS_PATH: _render(questions),
        RUBRICS_PATH: _render(rubrics),
        MANIFEST_PATH: _render(_manifest(CSV_PATH, rubrics)),
    }
    if args.check:
        drifted = [str(path) for path, content in outputs.items() if not path.exists() or path.read_text() != content]
        if drifted:
            raise SystemExit("generated FAB v2 artifacts drifted: " + ", ".join(drifted))
        return 0
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
