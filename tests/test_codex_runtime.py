from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from self_harness.codex import CodexRunResult, run_codex_agent
from self_harness.core import load_experiment

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "benchmarks" / "fabv2" / "workspace"
sys.path.insert(0, str(WORKSPACE))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


codex_runner = _load("codex_runner_under_test", WORKSPACE / "codex_runner.py")


def test_codex_adapter_records_command_events_and_usage(tmp_path: Path, monkeypatch):
    output = tmp_path / "last.md"

    def fake_run(argv, **kwargs):
        assert kwargs["cwd"] == tmp_path
        assert kwargs["env"] == {"TEST_ONLY": "1"}
        output.write_text("complete answer")
        event = {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 11,
                "cached_input_tokens": 3,
                "output_tokens": 5,
            },
        }
        return subprocess.CompletedProcess(argv, 0, json.dumps(event) + "\n", "")

    monkeypatch.setattr("self_harness.codex.subprocess.run", fake_run)
    result = run_codex_agent(
        command=["fake-codex"],
        model="test-model",
        prompt="solve",
        cwd=tmp_path,
        output_last_message=output,
        timeout_s=30,
        reasoning_effort="high",
        env={"TEST_ONLY": "1"},
    )

    assert result.returncode == 0
    assert result.final_text == "complete answer"
    assert result.usage == {
        "input_tokens": 11,
        "cached_input_tokens": 3,
        "output_tokens": 5,
    }
    assert result.argv[0] == "fake-codex"
    assert "workspace-write" in result.argv
    assert 'model_reasoning_effort="high"' in result.argv


def test_codex_adapter_returns_auditable_timeout(tmp_path: Path, monkeypatch):
    def fake_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output=b'{"type":"partial"}\n')

    monkeypatch.setattr("self_harness.codex.subprocess.run", fake_timeout)
    result = run_codex_agent(
        model="test-model",
        prompt="solve",
        cwd=tmp_path,
        output_last_message=tmp_path / "missing.md",
        timeout_s=7,
    )

    assert result.returncode == 124
    assert result.termination_reason == "timeout"
    assert result.events == ({"type": "partial"},)
    assert "timed out after 7s" in result.stderr
    assert result.final_text == ""


def test_fab_codex_runner_satisfies_evaluator_contract(tmp_path: Path, monkeypatch):
    captured = {}

    def fake_agent(**kwargs):
        captured.update(kwargs)
        (kwargs["cwd"] / "final_answer.md").write_text("42 with sources")
        Path(kwargs["env"]["FAB_TOOLS_USAGE_FILE"]).write_text(
            json.dumps({"calls": {"calculator": 2}, "errors": 0})
        )
        return CodexRunResult(
            argv=("codex",),
            returncode=0,
            duration_s=1.5,
            events=(
                {"type": "item.completed", "item": {"type": "agent_message"}},
                {"type": "item.completed", "item": {"type": "command_execution"}},
            ),
            stderr="",
            final_text="fallback",
            usage={"input_tokens": 20, "cached_input_tokens": 4, "output_tokens": 6},
        )

    monkeypatch.setattr(codex_runner, "run_codex_agent", fake_agent)
    monkeypatch.setenv("FABV2_CACHE", str(tmp_path / "missing-cache"))
    output = codex_runner.run_question(
        "Compute the answer.",
        model="test-model",
        log_dir=tmp_path / "trajectory",
        max_turns=1,
        max_time=60,
        max_tokens=100,
    )

    case_root = captured["cwd"]
    assert (case_root / "task.md").read_text().endswith("Compute the answer.\n")
    assert "Frozen FAB v2 harness" in (case_root / "AGENTS.md").read_text()
    assert output["final_answer"] == "42 with sources"
    assert output["tokens"] == 26
    assert output["turns"] == 1
    assert output["tool_calls_count"] == 1
    assert output["tool_usage"] == {"calculator": 2}
    assert output["stop_reason"] == "completed"
    assert json.loads((tmp_path / "trajectory" / "codex_run.json").read_text())["returncode"] == 0


def test_codex_fab_contracts_are_explicit_and_complete():
    hard4 = load_experiment(ROOT / "configs" / "fabv2_codex_hard4.toml")
    public27 = load_experiment(ROOT / "configs" / "fabv2_codex_public27_strong.toml")

    assert hard4.runner_config["env"]["FABV2_INNER_RUNTIME"] == "codex"
    assert hard4.model == "gpt-5.6-sol"
    assert len(hard4.cases) == 4
    assert public27.runner_config["env"]["FABV2_INNER_RUNTIME"] == "codex"
    assert public27.model == "gpt-5.6-sol"
    assert public27.repeats == 3
    assert len(public27.cases) == 27
