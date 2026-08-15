from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from self_harness.agent import ProposerWorkspace
from self_harness.core import RunLayout
from self_harness.pi import build_atomic_context, invoke_pi_proposer, parse_atomic_proposal
from self_harness.prime import PrimeRunResult


def _workspace(tmp_path: Path) -> ProposerWorkspace:
    current = tmp_path / "current"
    current.mkdir()
    surface = current / "system.md"
    surface.write_text("old\n")
    (tmp_path / "task.md").write_text("visible task\n")
    (tmp_path / "failure_clusters.json").write_text("[]\n")
    (tmp_path / "experience").mkdir()
    (tmp_path / "experience" / "records.jsonl").write_text('{"case_id":"train-1"}\n')
    proposal = tmp_path / "proposal.md"
    proposal.write_text("template\n")
    return ProposerWorkspace(tmp_path, current, proposal, {"system": surface})


def test_atomic_context_contains_visible_evidence_and_surfaces(tmp_path: Path):
    context = build_atomic_context(_workspace(tmp_path))
    assert "visible task" in context
    assert '"case_id":"train-1"' in context
    assert "## system\nold" in context


def test_parse_atomic_proposal_rejects_undeclared_surface():
    payload = {
        "summary": "change",
        "root_cause": "cause",
        "evidence": [],
        "flip_to_pass": [],
        "at_risk": [],
        "edits": {"evaluator": "disable"},
    }
    with pytest.raises(RuntimeError, match="undeclared surfaces"):
        parse_atomic_proposal(json.dumps(payload), allowed_surfaces={"system"})


def test_pi_proposal_is_applied_only_after_valid_complete_json(tmp_path: Path, monkeypatch):
    workspace = _workspace(tmp_path)
    payload = {
        "summary": "budget-aware research",
        "root_cause": "repeated reads consume the submission reserve",
        "evidence": ["train-1 reached the token limit"],
        "flip_to_pass": ["train-1"],
        "at_risk": [],
        "edits": {"system": "new policy"},
    }
    result = PrimeRunResult(
        argv=("pi",),
        returncode=0,
        duration_s=1.0,
        events=(),
        stderr="",
        final_text=json.dumps(payload),
        usage={"model_calls": 1, "total_tokens": 100},
    )
    monkeypatch.setattr("self_harness.pi.run_pi_agent", lambda **_kwargs: result)
    experiment = SimpleNamespace(
        better_agent_config={},
        better_agent_model="provider/model",
        better_agent_system_prompt=None,
    )

    invoke_pi_proposer(experiment=experiment, workspace=workspace)

    assert workspace.surface_files["system"].read_text() == "new policy\n"
    proposal = workspace.proposal_file.read_text()
    assert "budget-aware research" in proposal
    assert '"root_cause": "repeated reads consume the submission reserve"' in proposal
    assert (tmp_path / "proposal_context.md").exists()


def test_invalid_pi_output_cannot_partially_edit_workspace(tmp_path: Path, monkeypatch):
    workspace = _workspace(tmp_path)
    result = PrimeRunResult(
        argv=("pi",),
        returncode=0,
        duration_s=1.0,
        events=(),
        stderr="",
        final_text="not json",
        usage={"model_calls": 1, "total_tokens": 10},
    )
    monkeypatch.setattr("self_harness.pi.run_pi_agent", lambda **_kwargs: result)
    experiment = SimpleNamespace(
        better_agent_config={},
        better_agent_model="provider/model",
        better_agent_system_prompt=None,
    )

    with pytest.raises(ValueError, match="valid JSON"):
        invoke_pi_proposer(experiment=experiment, workspace=workspace)
    assert workspace.surface_files["system"].read_text() == "old\n"


def test_search_usage_counts_direct_proposals_but_not_copied_history(tmp_path: Path):
    layout = RunLayout(tmp_path)
    direct = layout.proposer_workspace_dir(1)
    direct.mkdir(parents=True)
    payload = {"usage": {"model_calls": 1, "total_tokens": 123, "cost": 0.5}}
    (direct / "outer_agent_result.json").write_text(json.dumps(payload))
    copied = direct / "history" / "prior_visible" / "proposer"
    copied.mkdir(parents=True)
    (copied / "outer_agent_result.json").write_text(json.dumps(payload))

    usage = layout.collect_search_usage()

    assert usage["model_calls"] == 1
    assert usage["total_tokens"] == 123
    assert usage["cost"] == 0.5
