from __future__ import annotations

import sys
from pathlib import Path

from better_harness.coding import CodingProjectRunner
from better_harness.core import (
    EvalCase,
    Experiment,
    Proposal,
    RunLayout,
    Surface,
    Variant,
    load_experiment,
    run_experiment,
)
from better_harness.ledger import Prediction
from better_harness.patching import build_variant


def _write_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    product = tmp_path / "product"
    product.mkdir()
    (product / "calculator.py").write_text("def add(a, b):\n    return a - b\n")
    (product / "test_product.py").write_text(
        "from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    )
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "fix-add.md").write_text("Fix the add function.\n")
    harness = tmp_path / "harness"
    harness.mkdir()
    (harness / "developer.md").write_text("Inspect the tests before editing.\n")
    agent = tmp_path / "agent.py"
    agent.write_text(
        "from pathlib import Path\n"
        "import os\n"
        "root = Path(os.environ['SELF_HARNESS_ROOT'])\n"
        "product = Path(os.environ['SELF_HARNESS_PRODUCT'])\n"
        "policy = (root / 'developer.md').read_text()\n"
        "if 'Inspect the tests' in policy:\n"
        "    p = product / 'calculator.py'\n"
        "    p.write_text(p.read_text().replace('a - b', 'a + b'))\n"
    )
    return product, tasks, harness, agent


def _experiment(tmp_path: Path, *, policy: str) -> tuple[Experiment, Variant]:
    product, tasks, harness, agent = _write_fixture(tmp_path)
    surface = Surface(
        name="developer",
        kind="workspace_file",
        target="developer.md",
        base_value=policy,
        filename="developer.md",
    )
    experiment = Experiment(
        path=tmp_path / "config.toml",
        name="coding-fixture",
        runner="coding",
        workspace_root=harness,
        model="fixture",
        max_iterations=1,
        better_agent_model="fixture",
        better_agent_max_turns=1,
        better_agent_deepagents_root=None,
        better_agent_system_prompt=None,
        runner_config={
            "product_root": str(product),
            "task_root": str(tasks),
            "agent_command": [sys.executable, str(agent)],
            "ci_commands": [[sys.executable, "-m", "pytest", "-q"]],
            "keep_workspaces": False,
        },
        surfaces={"developer": surface},
        cases=(
            EvalCase(case_id="fix-add.md", split="train", stratum="bugfix"),
            EvalCase(case_id="fix-add.md#holdout", split="holdout", stratum="bugfix"),
        ),
    )
    # Direct-run tests use the train case only; the synthetic holdout id exists
    # to keep the Experiment shape honest without duplicating fixture files.
    variant = Variant(
        label="candidate",
        model="fixture",
        changed_surfaces=("developer",),
        surfaces={"developer": surface},
        values={"developer": policy},
    )
    return experiment, variant


def test_coding_runner_edits_disposable_product_and_runs_external_ci(tmp_path):
    experiment, variant = _experiment(tmp_path, policy="Inspect the tests before editing.\n")
    result = CodingProjectRunner().run_split(
        experiment=experiment,
        variant=variant,
        split="train",
        layout=RunLayout(tmp_path / "run"),
    )
    assert result.passed == result.total == 1
    case_dir = Path(result.outcomes[0].artifacts_dir)
    assert not (case_dir / "product").exists()
    assert "calculator.py" in (case_dir / "product_diff.json").read_text()
    assert '"event": "ci_end"' in (case_dir / "trace.jsonl").read_text()
    # The immutable seed was not modified by the inner loop.
    assert "a - b" in Path(experiment.runner_config["product_root"]).joinpath("calculator.py").read_text()


def test_coding_runner_records_a_failed_product_without_mutating_seed(tmp_path):
    experiment, variant = _experiment(tmp_path, policy="Make a reasonable change.\n")
    result = CodingProjectRunner().run_split(
        experiment=experiment,
        variant=variant,
        split="train",
        layout=RunLayout(tmp_path / "run"),
    )
    assert result.passed == 0
    assert result.total == 1
    assert result.score == 0.0
    assert "assert -1 == 5" in (result.outcomes[0].failure_message or "")


def test_coding_config_loads_and_resolves_paths():
    root = Path(__file__).resolve().parents[1]
    experiment = load_experiment(root / "configs" / "coding_demo.toml")
    assert experiment.runner == "coding"
    assert Path(experiment.runner_config["product_root"]).is_absolute()
    assert experiment.goal.primary_metric == "score"


def test_outer_loop_improves_the_coding_harness_and_inner_product(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    experiment = load_experiment(root / "configs" / "coding_demo.toml")

    def propose(**kwargs):
        current = kwargs["current"]
        candidate = build_variant(
            experiment=experiment,
            label="iter-001-k00",
            values={
                **current.values,
                "developer": "Inspect and run the tests before and after editing.\n",
            },
        )
        proposal = Proposal(
            changed_surfaces=("developer",),
            workspace_dir=str(tmp_path),
            summary="Make tests part of the coding workflow.",
            final_message=None,
            prediction=Prediction(
                root_cause="The seed policy never directs the coding agent to inspect tests.",
                flip_to_pass=("fix-add.md", "fix-negative.md"),
            ),
        )
        return proposal, candidate

    monkeypatch.setattr("better_harness.agent.propose_variant", propose)
    report = run_experiment(experiment, output_dir=tmp_path / "dual-loop")
    assert report.baseline_train.passed == 0
    assert report.final_train.passed == 1
    assert report.final_holdout.passed == 1
    assert report.final_scorecard is not None
    assert report.final_scorecard.passed == 1
    seed = root / "benchmarks" / "coding" / "product" / "calculator.py"
    assert "a - b" in seed.read_text()
