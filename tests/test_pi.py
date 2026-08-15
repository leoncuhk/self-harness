from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import self_harness.pi as pi_module
from self_harness.agent import ProposerWorkspace, candidate_search_role
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
    (tmp_path / "history").mkdir()
    (tmp_path / "history" / "visible_history.md").write_text(
        "Iteration 1 changed tools; train 0/1.\n"
    )
    (tmp_path / "history" / "prior_attempts.json").write_text(
        '[{"iteration":1,"hypothesis":"output too large"}]\n'
    )
    proposal = tmp_path / "proposal.md"
    proposal.write_text("template\n")
    return ProposerWorkspace(tmp_path, current, proposal, {"system": surface})


def test_atomic_context_contains_visible_evidence_and_surfaces(tmp_path: Path):
    context = build_atomic_context(_workspace(tmp_path))
    assert "visible task" in context
    assert '"case_id":"train-1"' in context
    assert "Iteration 1 changed tools; train 0/1" in context
    assert '"hypothesis":"output too large"' in context
    assert "## system\nold" in context


def test_parallel_candidates_have_orthogonal_search_roles():
    assert candidate_search_role(0)[0] == "instruction/workflow"
    assert candidate_search_role(1)[0] == "machine-enforced policy"
    assert "runtime_policy" in candidate_search_role(1)[1]
    assert candidate_search_role(4) == candidate_search_role(0)


def test_outer_retries_empty_transport_failure_and_accounts_attempts(monkeypatch):
    failed = PrimeRunResult(
        argv=("pi",),
        returncode=0,
        duration_s=1,
        events=({"type": "auto_retry_end", "success": False, "finalError": "Connection error."},),
        stderr="",
        final_text="",
        usage={"total_tokens": 0},
    )
    succeeded = PrimeRunResult(
        argv=("pi",),
        returncode=0,
        duration_s=1,
        events=(),
        stderr="",
        final_text="{}",
        usage={"total_tokens": 10},
    )
    queue = iter((failed, succeeded))
    monkeypatch.setattr(pi_module, "run_pi_agent", lambda **_kwargs: next(queue))

    def immediate_retry(call, **_kwargs):
        with pytest.raises(RuntimeError, match="Connection error"):
            call()
        return call()

    monkeypatch.setattr(pi_module, "retry_transient", immediate_retry)

    result, attempts = pi_module._run_pi_transport_safe(label="test")  # noqa: SLF001

    assert result is succeeded
    assert attempts == (failed, succeeded)


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


def test_pi_budget_exhaustion_is_persisted_as_noop(tmp_path: Path, monkeypatch):
    workspace = _workspace(tmp_path)
    result = PrimeRunResult(
        argv=("pi",),
        returncode=125,
        duration_s=1.0,
        events=(),
        stderr="Prime Agent stopped at hard max_tokens budget",
        final_text="",
        usage={"model_calls": 1, "total_tokens": 60_000},
    )
    monkeypatch.setattr("self_harness.pi.run_pi_agent", lambda **_kwargs: result)
    experiment = SimpleNamespace(
        better_agent_config={},
        better_agent_model="provider/model",
        better_agent_system_prompt=None,
    )

    assert invoke_pi_proposer(experiment=experiment, workspace=workspace) is None
    assert workspace.surface_files["system"].read_text() == "old\n"
    failure = json.loads((tmp_path / "proposal_failure.json").read_text())
    assert failure["kind"] == "proposer_budget_exhausted"
    assert "Surfaces changed: none" in workspace.proposal_file.read_text()


def test_invalid_json_gets_one_syntax_only_repair(tmp_path: Path, monkeypatch):
    workspace = _workspace(tmp_path)
    valid = json.dumps(
        {
            "summary": "fixed syntax",
            "root_cause": "bounded cause",
            "evidence": ["train-1"],
            "flip_to_pass": ["train-1"],
            "at_risk": [],
            "edits": {"system": "repaired policy"},
        }
    )
    results = iter(
        [
            PrimeRunResult(
                argv=("pi",),
                returncode=0,
                duration_s=1.0,
                events=(),
                stderr="",
                final_text='{"broken": "json}',
                usage={"model_calls": 1, "total_tokens": 100},
            ),
            PrimeRunResult(
                argv=("pi",),
                returncode=0,
                duration_s=1.0,
                events=(),
                stderr="",
                final_text=valid,
                usage={"model_calls": 1, "total_tokens": 40},
            ),
        ]
    )
    monkeypatch.setattr("self_harness.pi.run_pi_agent", lambda **_kwargs: next(results))
    experiment = SimpleNamespace(
        better_agent_config={},
        better_agent_model="provider/model",
        better_agent_system_prompt=None,
    )

    invoke_pi_proposer(experiment=experiment, workspace=workspace)

    assert workspace.surface_files["system"].read_text() == "repaired policy\n"
    persisted = json.loads((tmp_path / "outer_agent_result.json").read_text())
    assert persisted["usage"]["model_calls"] == 2
    assert persisted["usage"]["total_tokens"] == 140
    assert "repair" in persisted


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
