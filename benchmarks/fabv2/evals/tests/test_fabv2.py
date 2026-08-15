"""FAB v2 public-development cases.

Run the inner finance agent on a question, judge with the
frozen deterministic evaluator, assert on the numeric-track partial credit.

Pass rule (frozen): partial_credit >= 0.75 on the deterministic numeric track
(dealbreaker gating is inside partial_credit: any failed must_pass -> 0).

The failure message carries the failed criteria verbatim so the outer loop's
failure-signature machinery has real material to cluster.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = Path(os.environ.get("BETTER_HARNESS_WORKSPACE_ROOT", ROOT.parent / "workspace"))
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(ROOT / "frozen"))

import agent_runner  # noqa: E402  (workspace module)
import judge  # noqa: E402  (frozen evaluator)

QUESTIONS = json.loads((ROOT.parent / "questions.json").read_text())
PROMPT = (WORKSPACE / "prompt.txt").read_text()
CRITERIA_TEXTS = [
    c["text"]
    for q in json.loads((ROOT / "frozen" / "rubrics.json").read_text())
    for c in q["criteria"]
]


# evaluator-side anti-memorisation guard: the prompt surface must not share any
# 8-word shingle with any grading criterion (semantic extension of case_id_leak)
def _shingles(text: str, n: int = 8) -> set[str]:
    words = re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


CRITERIA_SHINGLES = set().union(*(_shingles(t) for t in CRITERIA_TEXTS))


def test_rubric_leak_guard() -> None:
    overlap = _shingles(PROMPT) & CRITERIA_SHINGLES
    assert not overlap, (
        f"guard:rubric_leak prompt shares {len(overlap)} criteria shingles, e.g. {sorted(overlap)[:3]}"
    )


@pytest.mark.timeout(900)
@pytest.mark.parametrize("qid", sorted(QUESTIONS))
def test_question(  # noqa: PLR0913 - pytest fixtures define the benchmark contract
    qid: str,
    artifact_dir: Path,
    model: str,
    agent_limits: dict[str, int],
    record_usage,
    record_metrics,
) -> None:
    question = QUESTIONS[qid]
    out = agent_runner.run_question(
        question,
        model=model,
        log_dir=artifact_dir / "trajectory",
        prompt_file=WORKSPACE / "prompt.txt",
        **agent_limits,
    )
    (artifact_dir / "answer.txt").write_text(out["final_answer"])
    (artifact_dir / "run.json").write_text(json.dumps(out, indent=2, default=str))
    record_usage({"total_tokens": out["tokens"], "system_fingerprints": []})

    verdict = judge.score_question(qid, out["final_answer"] or "")
    (artifact_dir / "judge.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False))
    record_metrics(
        {
            "partial_credit": verdict["partial_credit"],
            "ungated_credit": verdict["ungated_credit"],
            "numeric_criterion_recall": verdict["numeric_criterion_recall"],
            "rubric_numeric_coverage": verdict["rubric_numeric_coverage"],
        }
    )

    summary = (
        f"fabv2:{qid} partial={verdict['partial_credit']:.3f} "
        f"(numeric {verdict['n_known']}/{verdict['n_criteria']}) "
        f"turns={out['turns']} stop={out['stop_reason']} tokens={out['tokens']}"
    )
    fails = "; ".join(verdict["failed_numeric"][:8]) or "none"
    assert verdict["partial_credit"] >= 0.75, f"{summary} | failed criteria: {fails}"
