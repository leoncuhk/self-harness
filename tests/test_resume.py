"""Resume correctness (A1/A2).

A crashed multi-hour stage has to be restartable, and the restart must not
invent evidence. Two failure modes are pinned here:

1. Candidate labels are positional (``iter-003``), so a resumed run reaches the
   same directory holding a *different* harness. Reusing on path alone would
   attribute old numbers to a new candidate — silently, and in the direction
   that looks like a working experiment.
2. Re-invoking the proposer on resume produces different surface values, which
   makes every downstream result unreusable and burns a model call per
   iteration. The proposal itself must therefore be reloaded, not re-asked.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from better_harness import runners as runners_module
from better_harness.agent import load_proposal_record, propose_variant
from better_harness.core import (
    CaseOutcome,
    RunLayout,
    SplitResult,
    load_experiment,
    main,
    reusable_result,
    run_experiment,
)
from better_harness.patching import build_baseline_variant, build_variant
from tests.test_better_harness import _write_minimal_pytest_experiment
from tests.test_e2e_full_loop import install_proposer, write_good_surfaces


def _load_agent_harness():
    """Import the frozen inner-agent builder by path (it is not a package)."""
    path = (
        Path(__file__).resolve().parents[1]
        / "benchmarks" / "agentic" / "workspace" / "agent_harness.py"
    )
    spec = importlib.util.spec_from_file_location("agent_harness_under_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_variant(tmp_path: Path, *, prompt: str):
    """Build a real variant off the demo fixture with one surface overridden."""
    config = _write_minimal_pytest_experiment(tmp_path / "fixture")
    experiment = load_experiment(config)
    baseline = build_baseline_variant(experiment)
    values = dict(baseline.values)
    values["prompt"] = prompt
    return experiment, build_variant(experiment=experiment, label="iter-001", values=values)


def write_result(path: Path, *, variant_key: str) -> SplitResult:
    result = SplitResult(
        split="train",
        variant=variant_key,
        model="demo",
        passed=4,
        total=4,
        score=4.0,
        returncode=0,
        run_dir=str(path.parent),
        outcomes=(
            CaseOutcome(
                case_id="tests/test_harness.py::test_prompt_train",
                split="train",
                stratum="prompt",
                status="passed",
                score=1.0,
                duration_s=1.0,
            ),
        ),
    )
    result.save(path)
    return result


def test_resume_reuses_a_result_only_for_the_same_harness(tmp_path):
    """Same label, same content: the stored result is reusable."""
    experiment, variant = make_variant(tmp_path, prompt="ask clarifying questions")
    layout = RunLayout(tmp_path / "run")
    variant_path = layout.variant_path(variant.key)
    variant.save(variant_path)
    split_dir = layout.split_dir(variant_key=variant.key, split="train")
    split_dir.mkdir(parents=True, exist_ok=True)
    result_path = split_dir / "result.json"
    write_result(result_path, variant_key=variant.key)

    reused = reusable_result(
        result_path=result_path,
        variant=variant,
        variant_path=variant_path,
    )
    assert reused is not None
    assert reused.passed == 4
    del experiment


def test_resume_refuses_a_result_measured_on_a_different_harness(tmp_path):
    """Same label, different content: reuse must be refused, not silently taken."""
    experiment, first = make_variant(tmp_path, prompt="ask clarifying questions")
    layout = RunLayout(tmp_path / "run")
    variant_path = layout.variant_path(first.key)
    first.save(variant_path)
    split_dir = layout.split_dir(variant_key=first.key, split="train")
    split_dir.mkdir(parents=True, exist_ok=True)
    result_path = split_dir / "result.json"
    write_result(result_path, variant_key=first.key)

    # What a resumed run actually produces: same positional label, new content.
    values = dict(first.values)
    values["prompt"] = "a completely different policy"
    second = build_variant(experiment=experiment, label="iter-001", values=values)
    assert second.key == first.key
    assert second.fingerprint != first.fingerprint

    assert (
        reusable_result(
            result_path=result_path,
            variant=second,
            variant_path=variant_path,
        )
        is None
    )


def test_resume_refuses_when_the_variant_record_is_missing_or_corrupt(tmp_path):
    """Unverifiable means re-run: absence of evidence is not evidence of a match."""
    _, variant = make_variant(tmp_path, prompt="ask clarifying questions")
    layout = RunLayout(tmp_path / "run")
    variant_path = layout.variant_path(variant.key)
    split_dir = layout.split_dir(variant_key=variant.key, split="train")
    split_dir.mkdir(parents=True, exist_ok=True)
    result_path = split_dir / "result.json"
    write_result(result_path, variant_key=variant.key)

    assert reusable_result(result_path=result_path, variant=variant, variant_path=variant_path) is None

    variant_path.parent.mkdir(parents=True, exist_ok=True)
    variant_path.write_text("{ not json")
    assert reusable_result(result_path=result_path, variant=variant, variant_path=variant_path) is None


def test_resume_retries_an_unmeasurable_apparatus_result(tmp_path):
    """A repaired environment must not reuse a prior failure to measure."""
    _, variant = make_variant(tmp_path, prompt="ask clarifying questions")
    layout = RunLayout(tmp_path / "run")
    variant_path = layout.variant_path(variant.key)
    variant.save(variant_path)
    result_path = layout.split_dir(variant_key=variant.key, split="train") / "result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    SplitResult(
        split="train",
        variant=variant.key,
        model="demo",
        passed=0,
        total=0,
        score=0.0,
        returncode=1,
        run_dir=str(result_path.parent),
        outcomes=(
            CaseOutcome(
                case_id="case",
                split="train",
                stratum="prompt",
                status="apparatus",
                score=0.0,
                duration_s=0.1,
                failure_message="[apparatus:provider_config] missing API key",
            ),
        ),
        apparatus=1,
    ).save(result_path)

    assert reusable_result(result_path=result_path, variant=variant, variant_path=variant_path) is None


def test_resume_refuses_a_changed_evaluation_contract(tmp_path):
    """Same harness under a different budget or case set is a new measurement."""
    experiment, variant = make_variant(tmp_path, prompt="ask clarifying questions")
    layout = RunLayout(tmp_path / "run")
    variant_path = layout.variant_path(variant.key)
    variant.save(variant_path)
    result_path = layout.split_dir(variant_key=variant.key, split="train") / "result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result = write_result(result_path, variant_key=variant.key)
    result = SplitResult(
        **{
            **result.__dict__,
            "evaluation_fingerprint": experiment.evaluation_fingerprint,
        }
    )
    result.save(result_path)

    assert reusable_result(
        result_path=result_path,
        variant=variant,
        variant_path=variant_path,
        evaluation_fingerprint="different-budget-fingerprint",
    ) is None


def test_evaluation_fingerprint_tracks_frozen_source_content(tmp_path):
    config = _write_minimal_pytest_experiment(tmp_path / "fixture")
    experiment = load_experiment(config)
    before = experiment.evaluation_fingerprint
    project_root = Path(str(experiment.runner_config["project_root"]))
    evaluator = next(project_root.rglob("test_*.py"))
    evaluator.write_text(evaluator.read_text() + "\n# evaluator revision\n")

    assert experiment.evaluation_fingerprint != before


def test_resume_reloads_the_proposal_instead_of_paying_for_another_model_call(tmp_path, monkeypatch):
    """A resumed iteration must not re-ask the proposer."""
    config = _write_minimal_pytest_experiment(tmp_path / "fixture")
    experiment = load_experiment(config)
    layout = RunLayout(tmp_path / "run")
    baseline = build_baseline_variant(experiment)
    train = SplitResult(
        split="train",
        variant="baseline",
        model=experiment.model,
        passed=0,
        total=1,
        score=0.0,
        returncode=1,
        run_dir=str(tmp_path),
        outcomes=(
            CaseOutcome(
                case_id="tests/test_harness.py::test_prompt_train",
                split="train",
                stratum="prompt",
                status="failed",
                score=0.0,
                duration_s=1.0,
                failure_message="assert 'ask' in prompt",
            ),
        ),
    )

    calls: list[int] = []

    def counting_proposer(*, experiment, workspace):
        del experiment
        calls.append(1)
        write_good_surfaces(workspace)
        workspace.proposal_file.write_text(
            "# Proposal\n\nFirst pass.\n\n"
            "```json\n"
            '{"root_cause": "empty surfaces", "evidence": ["prompt-train"],'
            ' "flip_to_pass": ["tests/test_harness.py::test_prompt_train"], "at_risk": []}\n'
            "```\n"
        )

    monkeypatch.setattr("better_harness.agent.invoke_deepagents_proposer", counting_proposer)

    first_proposal, first_variant = propose_variant(
        experiment=experiment,
        current=baseline,
        train_result=train,
        layout=layout,
        iteration=1,
    )
    assert len(calls) == 1

    second_proposal, second_variant = propose_variant(
        experiment=experiment,
        current=baseline,
        train_result=train,
        layout=layout,
        iteration=1,
        resume=True,
    )
    # No second model call, and the reloaded candidate is byte-identical, so the
    # evaluation results from the crashed attempt stay valid evidence.
    assert len(calls) == 1
    assert second_variant.fingerprint == first_variant.fingerprint
    assert second_proposal.prediction.flip_to_pass == first_proposal.prediction.flip_to_pass
    assert second_proposal.changed_surfaces == first_proposal.changed_surfaces


def test_load_proposal_record_returns_none_on_junk(tmp_path):
    path = tmp_path / "result.json"
    assert load_proposal_record(path) is None
    path.write_text("{ not json")
    assert load_proposal_record(path) is None
    path.write_text(json.dumps({"proposal": {}}))
    assert load_proposal_record(path) is None


def test_resumed_run_reaches_the_same_verdict_without_re_running_evaluations(tmp_path, monkeypatch):
    """End to end: a second run with --resume spends no proposer call and no eval."""
    install_proposer(
        monkeypatch,
        "# Proposal\n\nFix everything.\n\n"
        "```json\n"
        '{"root_cause": "surfaces were empty", "evidence": ["prompt-train"],'
        ' "flip_to_pass": ["tests/test_harness.py::test_prompt_train"], "at_risk": []}\n'
        "```\n",
    )
    config = _write_minimal_pytest_experiment(tmp_path / "fixture")
    output_dir = tmp_path / "run"
    first = run_experiment(load_experiment(config), output_dir=output_dir, max_iterations=1)

    spent: list[str] = []
    real_run_split = runners_module.PytestRunner.run_split

    def spy(self, **kwargs):
        result = real_run_split(self, **kwargs)
        if result.run_dir and Path(result.run_dir).exists():
            spent.append(f"{kwargs['variant'].key}/{kwargs['split']}")
        return result

    monkeypatch.setattr(runners_module.PytestRunner, "run_split", spy)

    second = run_experiment(
        load_experiment(config),
        output_dir=output_dir,
        max_iterations=1,
        reuse_existing=True,
    )
    assert second.final_train.correctness == first.final_train.correctness
    assert second.final_holdout.correctness == first.final_holdout.correctness


@pytest.mark.parametrize(
    ("text", "transient"),
    [
        ("Connection error.", True),
        ("Server disconnected without sending a response.", True),
        ("Error code: 502 - bad gateway", True),
        ("Request timed out", True),
        ("assert 'bolt   42' == 'bolt  42'", False),
        ("KeyError: 'answer.txt'", False),
    ],
)
def test_inner_agent_transient_classifier(text, transient):
    """Only transport noise is retried; a task failure must be graded, not retried."""
    assert _load_agent_harness().is_transient(RuntimeError(text)) is transient


def test_stage_output_withholds_the_sealed_scorecard(tmp_path, monkeypatch, capsys):
    """A stage log must not be able to spend the one pre-registered unseal."""
    install_proposer(
        monkeypatch,
        "# Proposal\n\nFix everything.\n\n"
        "```json\n"
        '{"root_cause": "surfaces were empty", "evidence": [],'
        ' "flip_to_pass": [], "at_risk": []}\n'
        "```\n",
    )
    config = _write_minimal_pytest_experiment(tmp_path / "fixture")
    output_dir = tmp_path / "run"

    assert main(["run", str(config), "--output-dir", str(output_dir), "--max-iterations", "1"]) == 0
    withheld = capsys.readouterr().out
    assert "| Locked test | *sealed* | *sealed* |" in withheld
    assert "Scorecard withheld from stdout" in withheld

    # The artifact on disk stays complete: reading it is a deliberate act.
    assert "| Locked test | `" in (output_dir / "report.md").read_text()

    assert (
        main(
            [
                "run",
                str(config),
                "--output-dir",
                str(output_dir),
                "--max-iterations",
                "1",
                "--resume",
                "--show-scorecard",
            ]
        )
        == 0
    )
    assert "| Locked test | `" in capsys.readouterr().out
