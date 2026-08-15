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
    assert (workspace / "prime_provider.ts").exists()
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
    }
    minimal = {path.name for path in (root / "minimal").iterdir()}
    strong = {path.name for path in (root / "strong").iterdir()}
    assert minimal == expected
    assert strong == expected
    assert sum((root / "strong" / name).stat().st_size for name in expected) > sum(
        (root / "minimal" / name).stat().st_size for name in expected
    )


def test_prime_smoke_contract_has_frozen_three_way_split():
    experiment = load_experiment(ROOT / "configs" / "fabv2_prime_smoke.toml")
    assert experiment.better_agent_backend == "prime"
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
    }
    assert experiment.goal.require_holdout_improvement
    assert experiment.better_agent_config["extensions"] == [
        str(
            (
                ROOT
                / "benchmarks"
                / "fabv2"
                / "workspace"
                / "prime_provider.ts"
            ).resolve()
        )
    ]
