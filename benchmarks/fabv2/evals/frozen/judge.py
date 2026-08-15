"""Frozen diagnostic evaluator for the FAB v2 public development set.

Mirrors the official Partial Credit semantics:
  - any failed must_pass (dealbreaker) criterion -> question score 0
  - otherwise severity-weighted average over criteria with numeric anchors
  - criteria without numeric anchors are 'unknown' (LLM track is deliberately
    not implemented here; decisions use the deterministic track only)

This is not the official Vals judge and cannot score qualitative criteria. Its
partial-credit-shaped output is a search signal, not an official benchmark
score. Frozen: do not edit during an experiment.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RUBRICS_PATH = Path(__file__).resolve().parent / "rubrics.json"

NUM_RE = re.compile(
    r"(?<![\d.,])(?P<neg>[-(]?)\$?(?P<num>\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s?(?P<unit>%|bps|basis points|x)?\)?(?!\d)"
)
TOL_REL, TOL_ABS = 0.005, 0.011
SCALE_MULT = {"": 1, "thousand": 1e3, "million": 1e6, "billion": 1e9}


def _looks_like_year(text: str, m: re.Match) -> bool:
    num = m.group("num")
    if "," in num or "." in num:
        return False
    value = int(num)
    before = text[: m.start()]
    after = text[m.end() :]
    if re.search(r"[-/.,]\s*$", before) or re.match(r"^[-/.,]\s?\d", after):
        return True
    if re.match(r"^A\b", after):
        return True
    if re.search(r"FY\s*$", before, re.IGNORECASE):
        return True
    return 1900 <= value <= 2035


def extract_anchors(text: str) -> list[dict]:
    anchors = []
    for m in NUM_RE.finditer(text):
        raw = m.group(0)
        num = m.group("num").replace(",", "")
        unit_raw = (m.group("unit") or "").strip()
        try:
            value = float(num)
        except ValueError:
            continue
        if _looks_like_year(text, m):
            continue
        if unit_raw == "" and not m.group("neg") and 0 <= value <= 9:
            continue
        neg = bool(m.group("neg")) or raw.strip().startswith("(")
        before = text[max(0, m.start() - 14) : m.start()].lower()
        if re.search(r"negative\s*\$?$|reduction\s+of\s+\$?$", before):
            neg = True
        if neg:
            value = -value
        unit = {"%": "percent", "bps": "bps", "basis points": "bps", "x": "multiple", "": "plain"}[
            unit_raw
        ]
        scale = ""
        m_scale = re.search(
            r"(million|billion|thousand)", text[m.end() : m.end() + 22], re.IGNORECASE
        )
        if m_scale:
            scale = m_scale.group(1).lower()
        anchors.append({"value": value, "unit": unit, "scale": scale, "raw": raw.strip()})
    return anchors


def match_anchor(anchor: dict, nums: list[dict]) -> bool:
    target = anchor["value"] * SCALE_MULT.get(anchor.get("scale", ""), 1)
    tol = max(TOL_ABS, abs(target) * TOL_REL)
    for n in nums:
        for factor in (1, 1e3, 1e6, 1e9):
            for cand in (n["value"], n["value"] * factor):
                if abs(cand - target) <= tol:
                    return True
    return False


def _load() -> dict[str, dict]:
    return {q["id"]: q for q in json.loads(RUBRICS_PATH.read_text())}


def score_question(qid: str, answer: str) -> dict:
    q = _load()[qid]
    nums = extract_anchors(answer or "")
    crit_results = []
    for c in q["criteria"]:
        if c["numeric"]:
            hits = sum(1 for a in c["numeric"] if match_anchor(a, nums))
            crit_results.append(
                {
                    "text": c["text"],
                    "severity": c["severity"],
                    "must_pass": c["must_pass"],
                    "passed": hits == len(c["numeric"]),
                    "anchors_hit": f"{hits}/{len(c['numeric'])}",
                }
            )
        else:
            crit_results.append(
                {
                    "text": c["text"],
                    "severity": c["severity"],
                    "must_pass": c["must_pass"],
                    "passed": None,
                }
            )
    known = [c for c in crit_results if c["passed"] is not None]
    failed_must = [c for c in known if c["must_pass"] and not c["passed"]]
    ungated_credit = (
        0.0
        if not known
        else sum(c["severity"] * c["passed"] for c in known) / sum(c["severity"] for c in known)
    )
    numeric_criterion_recall = (
        0.0 if not known else sum(bool(c["passed"]) for c in known) / len(known)
    )
    partial = 0.0 if failed_must or not known else ungated_credit
    return {
        "qid": qid,
        "category": q["category"],
        "partial_credit": partial,
        "ungated_credit": ungated_credit,
        "numeric_criterion_recall": numeric_criterion_recall,
        "rubric_numeric_coverage": 0.0 if not q["criteria"] else len(known) / len(q["criteria"]),
        "n_known": len(known),
        "n_criteria": len(q["criteria"]),
        "failed_must_pass": [c["text"][:100] for c in failed_must],
        "failed_numeric": [
            f"{'MUST ' if c['must_pass'] else ''}({c['anchors_hit']}) {c['text'][:110]}"
            for c in known
            if not c["passed"]
        ],
        "criteria": crit_results,
    }
