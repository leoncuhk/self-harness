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

import judge  # noqa: E402  (frozen evaluator)
import telemetry  # noqa: E402  (frozen evaluator)

RUNTIME = os.environ.get("FABV2_INNER_RUNTIME", "prime").strip().lower()
if RUNTIME == "prime":
    import prime_runner as inner_runner
elif RUNTIME == "codex":
    import codex_runner as inner_runner
else:
    raise RuntimeError(f"unsupported FABV2_INNER_RUNTIME {RUNTIME!r}")

QUESTIONS = json.loads((ROOT.parent / "questions.json").read_text())
PROMPT = inner_runner.compose_harness_prompt(WORKSPACE)
CRITERIA_TEXTS = [
    c["text"]
    for q in json.loads((ROOT / "frozen" / "rubrics.json").read_text())
    for c in q["criteria"]
]


# Evaluator-side anti-memorisation guard: the complete runtime harness (prompt
# plus enabled policy surfaces) must not share any 8-word shingle with a rubric.
def _shingles(text: str, n: int = 8) -> set[str]:
    words = re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


CRITERIA_SHINGLES = set().union(*(_shingles(t) for t in CRITERIA_TEXTS))


def test_rubric_leak_guard() -> None:
    overlap = _shingles(PROMPT) & CRITERIA_SHINGLES
    assert not overlap, (
        f"guard:rubric_leak prompt shares {len(overlap)} criteria shingles, e.g. {sorted(overlap)[:3]}"
    )


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
    out = inner_runner.run_question(
        question,
        model=model,
        log_dir=artifact_dir / "trajectory",
        **agent_limits,
    )
    (artifact_dir / "answer.txt").write_text(out["final_answer"])
    (artifact_dir / "run.json").write_text(json.dumps(out, indent=2, default=str))
    record_usage({"total_tokens": out["tokens"], "system_fingerprints": []})

    verdict = judge.score_question(qid, out["final_answer"] or "")
    (artifact_dir / "judge.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False))
    metrics = {
        "partial_credit": verdict["partial_credit"],
        "ungated_credit": verdict["ungated_credit"],
        "numeric_criterion_recall": verdict["numeric_criterion_recall"],
        "rubric_numeric_coverage": verdict["rubric_numeric_coverage"],
    }
    metrics.update(telemetry.behavior_metrics(out))
    record_metrics(metrics)

    usage = out.get("tool_usage") or {}
    summary = (
        f"fabv2:{qid} partial={verdict['partial_credit']:.3f} "
        f"(numeric {verdict['n_known']}/{verdict['n_criteria']}) "
        f"turns={out['turns']} calls={out['tool_calls_count']} errors={out['error_count']} "
        f"edgar/fetch/calc={usage.get('edgar_search', 0)}/{usage.get('fetch_page_text', 0)}/"
        f"{usage.get('calculator', 0)} stop={out['stop_reason']} tokens={out['tokens']}"
    )
    fails = "; ".join(verdict["failed_numeric"][:8]) or "none"
    assert verdict["partial_credit"] >= 0.75, f"{summary} | failed criteria: {fails}"
