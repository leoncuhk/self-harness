import ast
import importlib.util
import json
from pathlib import Path

from better_harness.core import load_experiment

ROOT = Path(__file__).resolve().parents[1]


def _builder_module():
    path = ROOT / "benchmarks" / "fabv2" / "tools" / "build_public_data.py"
    spec = importlib.util.spec_from_file_location("fabv2_build_public_data", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public27_artifacts_match_pinned_source():
    builder = _builder_module()
    questions, rubrics = builder.build()
    root = ROOT / "benchmarks" / "fabv2"

    assert len(questions) == 27
    assert len(rubrics) == 27
    assert sum(len(question["criteria"]) for question in rubrics) == 239
    assert sum(
        criterion["must_pass"]
        for question in rubrics
        for criterion in question["criteria"]
    ) == 79
    assert json.loads((root / "questions.json").read_text()) == questions
    assert json.loads((root / "evals" / "frozen" / "rubrics.json").read_text()) == rubrics


def test_seed_prompt_matches_the_archived_official_harness():
    source = (
        ROOT
        / "research"
        / "zcode"
        / "upstream"
        / "finance-agent-v2"
        / "finance_agent"
        / "prompt.py"
    )
    syntax = ast.parse(source.read_text())
    official_prompt = None
    for node in syntax.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "SYSTEM_PROMPT"
            for target in node.targets
        ):
            official_prompt = ast.literal_eval(node.value)
            break

    assert official_prompt is not None
    seed_prompt = (ROOT / "benchmarks" / "fabv2" / "workspace" / "prompt.txt").read_text()
    assert seed_prompt.strip() == official_prompt.strip()


def test_public27_has_three_questions_in_each_of_nine_categories():
    manifest = json.loads(
        (ROOT / "benchmarks" / "fabv2" / "data" / "manifest.json").read_text()
    )

    assert manifest["evaluation_status"] == "public-development-only"
    assert manifest["source_sha256"] == (
        "27b48c08a6099bc076b4194cac7cefe295082b9aedcbc67f4fedfa70468b427e"
    )
    assert len(manifest["categories"]) == 9
    assert set(manifest["categories"].values()) == {3}


def test_public27_experiment_is_complete_stratified_adaptive_development():
    experiment = load_experiment(ROOT / "configs" / "fabv2_public27_self_harness.toml")
    folds = json.loads(
        (
            ROOT
            / "benchmarks"
            / "fabv2"
            / "community"
            / "development_folds.json"
        ).read_text()
    )

    assert experiment.repeats == 3
    assert len(experiment.cases_for_split("train")) == 18
    assert len(experiment.cases_for_split("holdout")) == 9
    assert not experiment.has_split("scorecard")
    assert len(experiment.strata_for_split("train")) == 9
    assert len(experiment.strata_for_split("holdout")) == 9
    assert len(folds["folds"]) == 3
    assert all(len(fold["train"]) == 18 for fold in folds["folds"])
    assert all(len(fold["holdout"]) == 9 for fold in folds["folds"])


def test_public27_fixed_comparators_share_the_execution_contract():
    evolved = load_experiment(ROOT / "configs" / "fabv2_public27_self_harness.toml")
    comparators = [
        load_experiment(ROOT / "configs" / "fabv2_public27_b0.toml"),
        load_experiment(ROOT / "configs" / "fabv2_public27_b5.toml"),
    ]

    for comparator in comparators:
        assert comparator.max_iterations == 0
        assert comparator.model == evolved.model
        assert comparator.repeats == evolved.repeats
        assert comparator.runner_config == evolved.runner_config
        assert comparator.cases == evolved.cases
        assert set(comparator.surfaces) == {"prompt"}


def test_numeric24_v5_has_stratified_locked_test_and_generalization_gate():
    evolved = load_experiment(
        ROOT / "configs" / "fabv2_numeric24_self_harness_v5.toml"
    )

    assert evolved.repeats == 3
    assert len(evolved.cases_for_split("train")) == 8
    assert len(evolved.cases_for_split("holdout")) == 8
    assert len(evolved.cases_for_split("scorecard")) == 8
    assert len(evolved.strata_for_split("train")) == 8
    assert len(evolved.strata_for_split("holdout")) == 8
    assert len(evolved.strata_for_split("scorecard")) == 8
    assert evolved.goal.require_holdout_improvement
    assert evolved.goal.min_delta == 0.03
    assert not evolved.goal.constraints
    assert evolved.runner_config["env"]["FABV2_RECOVERY_SUBMIT"] == "1"
    assert "--timeout=1050" in evolved.runner_config["pytest_args"]
    assert evolved.runner_config["case_timeout_s"] == 1080


def test_numeric24_v5_seed_is_official_prompt_and_b5_is_contract_matched():
    evolved = load_experiment(
        ROOT / "configs" / "fabv2_numeric24_self_harness_v5.toml"
    )
    comparator = load_experiment(ROOT / "configs" / "fabv2_numeric24_b5_v5.toml")

    assert evolved.surfaces["prompt"].base_value == (
        ROOT / "benchmarks" / "fabv2" / "workspace" / "prompt.txt"
    ).read_text().strip()
    assert all(
        not evolved.surfaces[name].base_value
        for name in ("research_policy", "verification_policy", "submission_policy")
    )
    assert comparator.max_iterations == 0
    assert comparator.model == evolved.model
    assert comparator.repeats == evolved.repeats
    assert comparator.runner_config == evolved.runner_config
    assert comparator.cases == evolved.cases
    assert comparator.goal == evolved.goal
