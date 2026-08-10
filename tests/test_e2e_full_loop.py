"""End-to-end checks that the full loop wires P0-P2 together.

Reuses the upstream pytest demo fixture and drives it through the real
``run_experiment`` with a fake outer agent, so the assertions cover the pieces
only the assembled loop can show: predictions surviving into the ledger, the
guard rejecting a candidate before it costs an evaluation, and K>1 producing one
decision record per candidate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from better_harness import runners as runners_module
from better_harness.core import load_experiment, run_experiment
from tests.test_better_harness import _write_minimal_pytest_experiment

GOOD_PROMPT = (
    "If the request is ambiguous, ask questions before acting.\n\n"
    "## Clarifying Requests\n\n"
    "- If a request is underspecified, ask only the minimum number of followup "
    "questions needed to take the next useful action.\n"
    "- Do not ask for details the user already supplied.\n"
    "- Use reasonable defaults when the request clearly implies them.\n"
)
GOOD_TOOLS = '"""Demo tool surface."""\n\nTOOLS = ["run_shell", "send_report"]\n'
GOOD_SKILLS = (
    "# Demo skills\n\n"
    "Be generally helpful.\n\n"
    "- Ask domain-defining questions before implementation questions.\n"
    "- First clarify the domain before proposing execution details.\n"
)
GOOD_MIDDLEWARE = (
    '"""Demo middleware surface."""\n\n'
    'MIDDLEWARE = ["duplicate tool calls", "reuse prior successful results"]\n'
)


def write_good_surfaces(workspace) -> None:
    """Write the surface values the demo evals expect."""
    (workspace.current_dir / "prompt.txt").write_text(GOOD_PROMPT)
    (workspace.current_dir / "tools.py").write_text(GOOD_TOOLS)
    (workspace.current_dir / "skills.md").write_text(GOOD_SKILLS)
    (workspace.current_dir / "middleware.py").write_text(GOOD_MIDDLEWARE)


def install_proposer(monkeypatch: pytest.MonkeyPatch, proposal_body: str) -> None:
    """Install a fake outer agent that always writes the passing surfaces."""

    def fake_proposer(*, experiment, workspace):
        del experiment
        write_good_surfaces(workspace)
        workspace.proposal_file.write_text(proposal_body)

    monkeypatch.setattr("better_harness.agent.invoke_deepagents_proposer", fake_proposer)


def run_demo(tmp_path: Path, *, name: str, overrides: str = "", max_iterations: int = 2):
    """Run the demo fixture through the real loop."""
    config = _write_minimal_pytest_experiment(tmp_path / "fixture")
    if overrides:
        config.write_text(config.read_text() + "\n" + overrides + "\n")
    output_dir = tmp_path / name
    report = run_experiment(load_experiment(config), output_dir=output_dir, max_iterations=max_iterations)
    return report, output_dir


def read_ledger(output_dir: Path) -> dict:
    return json.loads((output_dir / "ledger.json").read_text())


def test_prediction_survives_into_the_ledger_and_is_graded(tmp_path, monkeypatch):
    """A prediction written in proposal.md must be parsed, stored, and scored."""
    install_proposer(
        monkeypatch,
        "# Proposal\n\nFix everything.\n\n"
        "```json\n"
        '{"root_cause": "surfaces were empty",'
        ' "evidence": ["prompt-train"],'
        ' "flip_to_pass": ["tests/test_harness.py::test_prompt_train"],'
        ' "at_risk": []}\n'
        "```\n",
    )
    _, output_dir = run_demo(tmp_path, name="run-pred")

    ledger = read_ledger(output_dir)
    assert ledger["summary"]["predictions_made"] >= 1

    first = ledger["entries"][0]
    assert first["prediction_made"] is True
    assert first["prediction"]["root_cause"] == "surfaces were empty"
    # The prediction named a case that really does flip, so it must be scored a hit.
    assert first["score"]["predicted"] == 1
    assert first["score"]["hits"] == 1
    assert first["score"]["precision"] == pytest.approx(1.0)
    assert (output_dir / "ledger.md").exists()


def test_missing_prediction_is_recorded_not_fatal(tmp_path, monkeypatch):
    """A proposer that skips the block still runs; the ledger records the omission."""
    install_proposer(monkeypatch, "# Proposal\n\nNo prediction block here.\n")
    report, output_dir = run_demo(tmp_path, name="run-nopred")

    ledger = read_ledger(output_dir)
    assert ledger["summary"]["predictions_made"] == 0
    assert ledger["entries"][0]["prediction_made"] is False
    # The loop still promoted the edit on its own merits.
    assert report.final_train.correctness == 1.0


def test_guard_rejects_a_leaky_candidate_without_spending_an_eval(tmp_path, monkeypatch):
    """A candidate that hard-codes a case id must never reach the runner."""
    evaluated: list[str] = []

    def counting_proposer(*, experiment, workspace):
        del experiment
        write_good_surfaces(workspace)
        # Leak a real eval case id into the harness text.
        (workspace.current_dir / "prompt.txt").write_text(
            GOOD_PROMPT + "\nAlways special-case tests/test_harness.py::test_prompt_train.\n"
        )
        workspace.proposal_file.write_text("# Proposal\n\nHardcoded the answer.\n")

    monkeypatch.setattr("better_harness.agent.invoke_deepagents_proposer", counting_proposer)

    real_run_split = runners_module.PytestRunner.run_split

    def spy(self, **kwargs):
        evaluated.append(kwargs["variant"].key)
        return real_run_split(self, **kwargs)

    monkeypatch.setattr(runners_module.PytestRunner, "run_split", spy)

    report, output_dir = run_demo(tmp_path, name="run-guard", max_iterations=1)

    assert all(key == "baseline" for key in evaluated), evaluated
    entry = read_ledger(output_dir)["entries"][0]
    assert entry["accepted"] is False
    assert entry["guard"]["ok"] is False
    assert entry["guard"]["violations"][0]["kind"] == "case_id_leak"
    assert report.final.key == "baseline"


def test_k_candidates_each_get_their_own_record(tmp_path, monkeypatch):
    """K>1 must produce K workspaces and K ledger rows for one iteration."""
    install_proposer(monkeypatch, "# Proposal\n\nFix everything.\n")
    _, output_dir = run_demo(tmp_path, name="run-k", overrides="", max_iterations=1)

    single = len(read_ledger(output_dir)["entries"])

    config = _write_minimal_pytest_experiment(tmp_path / "fixture-k")
    original = config.read_text()
    patched = original.replace('name = "minimal-pytest"', 'name = "minimal-pytest"\ncandidates = 2', 1)
    assert patched != original, "fixture config shape changed; K override did not apply"
    config.write_text(patched)
    multi_dir = tmp_path / "run-k2"
    run_experiment(load_experiment(config), output_dir=multi_dir, max_iterations=1)

    entries = read_ledger(multi_dir)["entries"]
    assert len(entries) == 2 * single
    # At most one candidate may be promoted per iteration.
    assert sum(1 for entry in entries if entry["accepted"]) <= 1
    assert (multi_dir / "history" / "visible" / "iterations" / "001" / "k00").exists()
    assert (multi_dir / "history" / "visible" / "iterations" / "001" / "k01").exists()


def test_failure_clusters_reach_the_ledger(tmp_path, monkeypatch):
    """Baseline failures must be clustered and recorded alongside the decision."""
    install_proposer(monkeypatch, "# Proposal\n\nFix everything.\n")
    _, output_dir = run_demo(tmp_path, name="run-clusters", max_iterations=1)

    clusters = read_ledger(output_dir)["entries"][0]["signature_clusters"]
    assert clusters, "baseline failures should produce at least one cluster"
    assert {"signature", "key", "size", "case_ids"} <= set(clusters[0])
