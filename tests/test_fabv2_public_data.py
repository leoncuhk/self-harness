import importlib.util
import json
from pathlib import Path

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
