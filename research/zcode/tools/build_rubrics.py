#!/usr/bin/env python3
"""把官方 public.csv 转换为本地评分器可消费的 rubrics.json。

每条记录:
  id            q001..q027
  question      题目原文
  category      九类之一
  expert_mins   专家用时
  criteria[]    {text, severity, must_pass, numeric[]}
    numeric: 从判据文本确定性抽取的数值锚点（值/单位/是否负数）。
             含数值锚点的判据优先走确定性判分轨道，其余走 LLM 裁判轨道。
年份（FY2023 / 2023 等）不算数值锚点，会被剔除。
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent / "finance-agent-v2" / "data" / "public.csv"
OUT = Path(__file__).resolve().parent / "rubrics.json"

# 数值 token：可选负号/括号负数、可选 $、数字（可千分位、可小数）、可选单位后缀。
# 左边界防拆数字（FY2020 不拆成 202+0）；右边界只防数字，允许 "32.82%."（%后跟句号）。
NUM_RE = re.compile(
    r"(?<![\d.,])(?P<neg>[-(]?)\$?(?P<num>\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s?(?P<unit>%|bps|basis points|x)?\)?(?!\d)",
)


def _looks_like_year(text: str, m: re.Match) -> bool:
    """日期/年份类数字不算答案数值：2023-01-01、12/31/2023、December 28, 2024、'21A-'24A。"""
    num = m.group("num")
    if "," in num or "." in num:
        return False
    value = int(num)
    before = text[: m.start()]
    after = text[m.end() :]
    # 日期片段的组成部分（无论数值大小）：左或右侧紧邻日期分隔符
    if re.search(r"[-/.,]\s*$", before) or re.match(r"^[-/.,]\s?\d", after):
        return True
    # '21A-'24A 这类财年标记后缀
    if re.match(r"^A\b", after):
        return True
    # FY 前缀（FY2023）或该区间内的裸整数（在判据文本里几乎总是年份）
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
        # "2-year"、"3-year" 这类序数噪音：无单位、无量纲、个位数的裸整数
        if unit_raw == "" and not m.group("neg") and 0 <= value <= 9:
            continue
        neg = bool(m.group("neg")) or raw.strip().startswith("(")
        # 词式负号：紧邻其前的 "negative" / "reduction of"
        before = text[max(0, m.start() - 14) : m.start()].lower()
        if re.search(r"negative\s*\$?$|reduction\s+of\s+\$?$", before):
            neg = True
        if neg:
            value = -value
        unit = {
            "%": "percent",
            "bps": "bps",
            "basis points": "bps",
            "x": "multiple",
            "": "plain",
        }[unit_raw]
        scale = ""
        m_scale = re.search(
            r"(million|billion|thousand|percent point|percentage point)",
            text[m.end() : m.end() + 22],
            re.IGNORECASE,
        )
        if m_scale:
            scale = m_scale.group(1).lower()
        anchors.append({"value": value, "unit": unit, "scale": scale, "raw": raw.strip()})
    return anchors


def main() -> None:
    rows = list(csv.DictReader(open(REPO)))
    out = []
    for i, r in enumerate(rows, 1):
        rubric = json.loads(r["Rubric"])
        criteria = [
            {
                "text": c["criteria"],
                "severity": c["modifiers"]["severity"],
                "must_pass": c["modifiers"].get("category") == "must_pass",
                "numeric": extract_anchors(c["criteria"]),
            }
            for c in rubric
        ]
        out.append(
            {
                "id": f"q{i:03d}",
                "question": r["Question"].replace("\n", " "),
                "category": r["Question Type"],
                "expert_mins": int(r["Expert time (mins)"]),
                "criteria": criteria,
            }
        )
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    n_crit = sum(len(q["criteria"]) for q in out)
    n_must = sum(c["must_pass"] for q in out for c in q["criteria"])
    n_num = sum(1 for q in out for c in q["criteria"] if c["numeric"])
    print(
        f"{len(out)} 题 / {n_crit} 判据 / {n_must} dealbreaker / {n_num} 判据含数值锚点"
        f"（{n_num / n_crit:.0%} 可走确定性判分）→ {OUT}"
    )


if __name__ == "__main__":
    main()
