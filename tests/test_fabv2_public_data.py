import importlib.util
import json
from pathlib import Path

from self_harness.core import load_experiment

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


def test_prime_runtime_replaces_the_archived_official_harness():
    workspace = ROOT / "benchmarks" / "fabv2" / "workspace"
    assert (workspace / "prime_runner.py").exists()
    assert (workspace / "fab_tools.py").exists()
    assert (workspace / "model_provider.ts").exists()
    assert (workspace / "runtime_policy.ts").exists()
    assert not (workspace / "agent_runner.py").exists()
    assert not (workspace / "prompt.txt").exists()


def test_minimal_and_strong_prime_harnesses_share_all_surfaces():
    root = ROOT / "benchmarks" / "fabv2" / "harnesses"
    expected = {
        "system.md",
        "orchestration.md",
        "tools.md",
        "research.md",
        "evidence.md",
        "subagents.md",
        "verification.md",
        "submission.md",
        "runtime_policy.json",
    }
    minimal = {path.name for path in (root / "minimal").iterdir()}
    strong = {path.name for path in (root / "strong").iterdir()}
    assert minimal == expected
    assert strong == expected
    assert sum((root / "strong" / name).stat().st_size for name in expected) > sum(
        (root / "minimal" / name).stat().st_size for name in expected
    )


def test_smoke_contract_has_frozen_three_way_split():
    experiment = load_experiment(ROOT / "configs" / "fabv2_smoke.toml")
    assert experiment.better_agent_backend == "pi"
    assert experiment.model == "self-harness/deepseek-v4-flash"
    assert experiment.repeats == 1
    assert len(experiment.cases_for_split("train")) == 1
    assert len(experiment.cases_for_split("holdout")) == 1
    assert len(experiment.cases_for_split("scorecard")) == 1
    assert set(experiment.surfaces) == {
        "system",
        "orchestration",
        "tools",
        "research",
        "evidence",
        "subagents",
        "verification",
        "submission",
        "runtime_policy",
    }
    assert experiment.goal.require_holdout_improvement
    assert experiment.better_agent_config["extensions"] == [
        str(
            (
                ROOT
                / "benchmarks"
                / "fabv2"
                / "workspace"
                / "model_provider.ts"
            ).resolve()
        )
    ]


def test_full_protocol_and_minimal_comparator_are_contract_matched():
    evolved = load_experiment(ROOT / "configs" / "fabv2.toml")
    minimal = load_experiment(ROOT / "configs" / "fabv2_minimal.toml")

    assert len(evolved.cases_for_split("train")) == 8
    assert len(evolved.cases_for_split("holdout")) == 8
    assert len(evolved.cases_for_split("scorecard")) == 8
    assert evolved.cases == minimal.cases
    assert evolved.runner_config == minimal.runner_config
    assert evolved.goal == minimal.goal
    assert evolved.model == minimal.model
    assert evolved.better_agent_backend == minimal.better_agent_backend == "pi"
    assert minimal.max_iterations == 0
    assert all(
        evolved.surfaces[name].base_value != minimal.surfaces[name].base_value
        for name in evolved.surfaces
        if name != "runtime_policy"
    )
    assert evolved.surfaces["runtime_policy"] == minimal.surfaces["runtime_policy"]


def test_evolution_smoke_has_visible_and_validation_headroom_cases():
    experiment = load_experiment(ROOT / "configs" / "fabv2_evolve_smoke.toml")
    assert [case.case_id for case in experiment.cases_for_split("train")] == [
        "tests/test_fabv2.py::test_question[q005]"
    ]
    assert [case.case_id for case in experiment.cases_for_split("holdout")] == [
        "tests/test_fabv2.py::test_question[q006]"
    ]
    assert [case.case_id for case in experiment.cases_for_split("scorecard")] == [
        "tests/test_fabv2.py::test_question[q004]"
    ]
    assert experiment.better_agent_backend == "pi"
    assert experiment.max_iterations == 1


def test_evolution_smoke_uses_atomic_single_call_proposer_budget():
    experiment = load_experiment(ROOT / "configs" / "fabv2_evolve_smoke.toml")
    assert experiment.better_agent_max_turns == 1
    assert experiment.better_agent_config["max_tokens"] == 60000


def test_live_evolution_claim_uses_replicated_selection():
    experiment = load_experiment(ROOT / "configs" / "fabv2_evolve_replicated.toml")

    assert experiment.repeats == 3
    assert experiment.max_iterations == 3
    assert experiment.candidates == 2


def test_replication_contracts_change_only_the_accepted_surfaces():
    strong = load_experiment(ROOT / "configs" / "fabv2_replicate_strong.toml")
    evolved = load_experiment(ROOT / "configs" / "fabv2_replicate_evolved.toml")

    assert strong.repeats == evolved.repeats == 3
    assert strong.max_iterations == evolved.max_iterations == 0
    assert strong.cases == evolved.cases
    assert strong.runner_config == evolved.runner_config
    assert strong.model == evolved.model
    changed = {
        name
        for name in strong.surfaces
        if strong.surfaces[name].base_value != evolved.surfaces[name].base_value
    }
    assert changed == {"orchestration", "verification"}


def test_public27_publication_arm_is_complete_and_frozen():
    experiment = load_experiment(ROOT / "configs" / "fabv2_public27_strong.toml")

    assert experiment.max_iterations == 0
    assert experiment.repeats == 3
    assert len(experiment.cases) == 27
    assert {case.case_id.rsplit("[", 1)[-1].removesuffix("]") for case in experiment.cases} == {
        f"q{index:03d}" for index in range(1, 28)
    }
