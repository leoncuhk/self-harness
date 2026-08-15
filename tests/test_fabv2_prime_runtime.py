from __future__ import annotations

import importlib.util
import json
import os
import shlex
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "benchmarks" / "fabv2" / "workspace"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fab_tools = _load("fab_tools_under_test", WORKSPACE / "fab_tools.py")
prime_runner = _load("prime_runner_under_test", WORKSPACE / "prime_runner.py")


def test_safe_calculator_records_usage(tmp_path: Path, monkeypatch):
    ledger = tmp_path / "usage.json"
    monkeypatch.setenv("FAB_TOOLS_USAGE_FILE", str(ledger))
    assert fab_tools.calculate("(10 - 2) * 3 / 4") == 6.0
    assert json.loads(ledger.read_text()) == {"calls": {"calculator": 1}}


def test_safe_calculator_rejects_code_execution(tmp_path: Path, monkeypatch):
    ledger = tmp_path / "usage.json"
    monkeypatch.setenv("FAB_TOOLS_USAGE_FILE", str(ledger))
    with pytest.raises(ValueError, match="unsupported"):
        fab_tools.calculate("__import__('os').getcwd()")
    assert json.loads(ledger.read_text())["errors"] == 1


def test_prime_runtime_isolates_case_and_reads_submission(tmp_path: Path, monkeypatch):
    fake = tmp_path / "fake_prime.py"
    fake.write_text(
        """
import json
from pathlib import Path

Path('final_answer.md').write_text('Answer: 42. Source: https://example.test/source\\n')
message = {
    'id': 'm1',
    'role': 'assistant',
    'content': [{'type': 'text', 'text': 'submitted'}],
    'usage': {
        'input': 10, 'output': 5, 'cacheRead': 1, 'cacheWrite': 2,
        'totalTokens': 18, 'cost': {'total': 0.02},
    },
    'stopReason': 'stop',
}
print(json.dumps({'type': 'message_end', 'message': message}))
print(json.dumps({'type': 'tool_execution_end', 'toolName': 'ipython', 'isError': False}))
print(json.dumps({'type': 'agent_end', 'messages': [message]}))
""".strip()
        + "\n"
    )
    monkeypatch.setenv(
        "PRIME_AGENT_COMMAND",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(fake))}",
    )
    monkeypatch.setenv("FABV2_CACHE", str(tmp_path / "cache"))

    out = prime_runner.run_question(
        "What is the answer?",
        model="openai/fake",
        log_dir=tmp_path / "artifacts",
        max_turns=5,
        max_time=30,
        max_tokens=1000,
    )

    assert out["runtime"] == "prime-agent"
    assert out["final_answer"].startswith("Answer: 42")
    assert out["success"]
    assert out["stop_reason"] == "submitted"
    assert out["tokens"] == 18
    assert out["cost"] == 0.02
    assert out["turns"] == 1
    assert out["tool_usage"] == {"ipython": 1, "submit_final_result": 1}
    case_root = tmp_path / "artifacts" / "prime_workspace"
    assert (case_root / "task.md").exists()
    assert (tmp_path / "artifacts" / "prime_result.json").exists()
    assert os.fspath(ROOT) not in (case_root / "task.md").read_text()


def test_prime_runtime_compiles_trace_when_research_does_not_submit(tmp_path: Path, monkeypatch):
    fake = tmp_path / "fake_compiler.py"
    fake.write_text(
        """
import json
import sys

is_compiler = '--no-tools' in sys.argv
text = 'Compiled answer: 17.15 percentage points. Source: https://example.test/filing' if is_compiler else 'research complete'
message = {
    'id': 'compiler' if is_compiler else 'research',
    'role': 'assistant',
    'content': [{'type': 'text', 'text': text}],
    'usage': {'input': 20, 'output': 10, 'totalTokens': 30, 'cost': {'total': 0.01}},
    'stopReason': 'stop',
}
print(json.dumps({'type': 'message_end', 'message': message}), flush=True)
if not is_compiler:
    print(json.dumps({'type': 'tool_execution_end', 'toolName': 'ipython', 'args': {},
                      'result': {'content': 'CRWD CAGR 32.82, PANW CAGR 15.67'},
                      'isError': False}), flush=True)
""".strip()
        + "\n"
    )
    monkeypatch.setenv(
        "PRIME_AGENT_COMMAND",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(fake))}",
    )

    out = prime_runner.run_question(
        "Which CAGR is higher?",
        model="openai/fake",
        log_dir=tmp_path / "artifacts",
        max_turns=6,
        max_time=30,
        max_tokens=1000,
    )

    assert out["compiler_used"]
    assert out["success"]
    assert out["final_answer"].startswith("Compiled answer")
    assert out["tokens"] == 60
    trace = tmp_path / "artifacts" / "prime_workspace" / "research_trace.json"
    assert "CRWD CAGR" in trace.read_text()


def test_strong_harness_has_all_runtime_surfaces():
    strong = ROOT / "benchmarks" / "fabv2" / "harnesses" / "strong"
    prompt = prime_runner.compose_harness_prompt(strong)
    for name in prime_runner.SURFACE_FILES:
        assert (strong / name).exists()
        assert name.removesuffix(".md").title() in prompt
