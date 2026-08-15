#!/usr/bin/env python3
"""本地评分器：模拟官方 Partial Credit / All-Pass 判分。

双轨制:
  - 确定性轨道: 判据含数值锚点 → 在答案文本中找数值，容差内判等
  - LLM 轨道:   无锚点的定性判据 → 需配 JUDGE_MODEL_API_KEY 后启用（待接入）

用法:
  python judge.py --selftest                 # 用"完美答案"自检评分管道（应 100%）
  python judge.py --results <results.json>   # 对一次真实运行的结果判分
输出: scores.json + 终端摘要（每题得分 / dealbreaker 命中 / 类别汇总）

判分规则对齐官方:
  Partial Credit = 任一 must_pass 判据 fail → 该题 0 分;
                   否则 = Σ(severity × pass) / Σ(severity)
  All-Pass       = 全部判据 pass 才 100%，否则 0
确定性轨道下未知的定性判据计为 pass=unknown，不参与 gating（乐观口径），
因此确定性分数是真实分数的【上界信号】，LLM 轨道接入后转为精确口径。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from build_rubrics import NUM_RE, extract_anchors

HERE = Path(__file__).resolve().parent
RUBRICS = HERE / "rubrics.json"

# 相对 0.5% 或绝对 0.011（两位小数舍入），取宽者
TOL_REL, TOL_ABS = 0.005, 0.011
SCALE_MULT = {"": 1, "thousand": 1e3, "million": 1e6, "billion": 1e9}


def numbers_in(answer: str) -> list[dict]:
    return extract_anchors(answer)


def match_anchor(anchor: dict, nums: list[dict]) -> bool:
    base = anchor["value"]
    mult = SCALE_MULT.get(anchor.get("scale", ""), 1)
    target = base * mult
    tol = max(TOL_ABS, abs(target) * TOL_REL)
    for n in nums:
        for factor in (1, 1e3, 1e6, 1e9):
            v = n["value"] * factor if mult > 1 else n["value"] / factor
            # 两种方向都试: 答案可能写成 6300.07 million 或 6,300,070,000
            for cand in (n["value"], n["value"] * factor):
                if abs(cand - target) <= tol:
                    return True
    return False


def score_question(q: dict, answer: str) -> dict:
    nums = numbers_in(answer)
    crit_results = []
    for c in q["criteria"]:
        if c["numeric"]:
            hits = sum(1 for a in c["numeric"] if match_anchor(a, nums))
            # 全部锚点命中才算该判据通过（锚点已过滤噪音，数量通常 1-3 个）
            passed = hits == len(c["numeric"])
            crit_results.append(
                {
                    "text": c["text"],
                    "severity": c["severity"],
                    "must_pass": c["must_pass"],
                    "track": "numeric",
                    "passed": passed,
                    "anchors_hit": f"{hits}/{len(c['numeric'])}",
                }
            )
        else:
            crit_results.append(
                {
                    "text": c["text"],
                    "severity": c["severity"],
                    "must_pass": c["must_pass"],
                    "track": "llm",
                    "passed": None,  # unknown，待 LLM 轨道
                }
            )
    known = [c for c in crit_results if c["passed"] is not None]
    unknown = [c for c in crit_results if c["passed"] is None]
    failed_must = [c for c in known if c["must_pass"] and not c["passed"]]
    if failed_must:
        partial = 0.0
    elif known:
        partial = sum(c["severity"] * c["passed"] for c in known) / sum(
            c["severity"] for c in known
        )
    else:
        partial = None
    all_pass = (
        all(c["passed"] for c in known) and not unknown if known else None
    )
    return {
        "id": q["id"],
        "category": q["category"],
        "partial_credit": partial,
        "all_pass": all_pass,
        "failed_must_pass": [c["text"][:80] for c in failed_must],
        "n_known": len(known),
        "n_unknown": len(unknown),
        "criteria": crit_results,
    }


def perfect_answer(q: dict) -> str:
    """自检用: 把判据原文拼成"完美答案"，数值锚点与定性表述必然全部在场。"""
    return "\n".join(f"- {c['text']}" for c in q["criteria"])


def summarize(results: list[dict]) -> None:
    scored = [r for r in results if r["partial_credit"] is not None]
    print(
        f"\n判分覆盖: {len(scored)}/{len(results)} 题（确定性轨道；LLM 轨道未启用）"
    )
    if scored:
        avg = sum(r["partial_credit"] for r in scored) / len(scored)
        print(f"Partial Credit（确定性上界口径）: {avg:.1%}")
        gated = [r for r in scored if r["partial_credit"] == 0.0]
        print(f"被 dealbreaker 归零的题: {len(gated)} {[r['id'] for r in gated]}")
        by_cat: dict[str, list[float]] = {}
        for r in scored:
            by_cat.setdefault(r["category"], []).append(r["partial_credit"])
        for cat, vals in sorted(by_cat.items()):
            print(f"  {cat:<30} {sum(vals) / len(vals):>6.1%}  (n={len(vals)})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--results", type=Path, help="harness 输出的 results.json")
    args = ap.parse_args()

    rubrics = {q["id"]: q for q in json.load(open(RUBRICS))}

    if args.selftest:
        out = [score_question(q, perfect_answer(q)) for q in rubrics.values()]
        bad = [
            r["id"]
            for r in out
            if r["partial_credit"] is not None and r["partial_credit"] < 1.0
        ]
        llm_only = [r["id"] for r in out if r["partial_credit"] is None]
        summarize(out)
        print(
            "\n自检:",
            "确定性轨道全部 100% ✓" if not bad else f"异常题目 {bad}",
        )
        print(f"纯定性题（需 LLM 轨道）: {llm_only} — 属预期，非失败")
        json.dump(out, open(HERE / "selftest_scores.json", "w"), indent=2)
        sys.exit(0 if not bad else 1)

    if not args.results:
        ap.error("需要 --results 或 --selftest")

    runs = json.load(open(args.results))
    out = []
    for i, run in enumerate(runs, 1):
        qid = f"q{i:03d}"
        answer = run.get("result", {}).get("final_answer", "") if run.get("success") else ""
        out.append(score_question(rubrics[qid], answer or ""))
    json.dump(out, open(HERE / "scores.json", "w"), indent=2)
    summarize(out)
    print("\n明细已写入 scores.json")


if __name__ == "__main__":
    main()
