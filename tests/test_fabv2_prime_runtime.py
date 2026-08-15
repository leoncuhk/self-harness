from __future__ import annotations

import importlib.util
import json
import os
import shlex
import sys
from pathlib import Path

import pytest

from self_harness.fab_policy import parse_fab_policy

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


def test_full_page_search_finds_text_beyond_fetch_prefix(tmp_path: Path, monkeypatch):
    ledger = tmp_path / "usage.json"
    monkeypatch.setenv("FAB_TOOLS_USAGE_FILE", str(ledger))
    document = b"<html><body>prefix " + (b"x" * 300_000) + b" Adjusted EBITDAR 123 </body></html>"
    monkeypatch.setattr(fab_tools, "_http", lambda _url: document)

    assert "Adjusted EBITDAR" not in fab_tools.fetch_page_text(
        "https://example.test", max_chars=1_000
    )
    matches = fab_tools.search_page_text(
        "https://example.test",
        ["adjusted ebitdar"],
        context_chars=100,
    )

    assert matches[0]["offset"] > 250_000
    assert "Adjusted EBITDAR 123" in matches[0]["snippet"]
    assert json.loads(ledger.read_text())["calls"] == {
        "fetch_page_text": 1,
        "search_page_text": 1,
    }


def test_full_page_search_ignores_inline_xbrl_hidden_metadata(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FAB_TOOLS_USAGE_FILE", str(tmp_path / "usage.json"))
    document = (
        b"<html><body><ix:header><ix:hidden>rent metadata noise</ix:hidden></ix:header>"
        b"<p>Annual rent payments were $113 million.</p></body></html>"
    )
    monkeypatch.setattr(fab_tools, "_http", lambda _url: document)

    matches = fab_tools.search_page_text("https://example.test", ["rent"], context_chars=100)

    assert len(matches) == 1
    assert "Annual rent payments" in matches[0]["snippet"]
    assert "metadata noise" not in matches[0]["snippet"]


def test_search_policy_is_machine_enforced_and_audited(tmp_path: Path, monkeypatch):
    ledger = tmp_path / "usage.json"
    monkeypatch.setenv("FAB_TOOLS_USAGE_FILE", str(ledger))
    monkeypatch.setattr(
        fab_tools,
        "_runtime_policy",
        lambda: {
            "schema_version": 1,
            "search_page": {
                "context_chars": 100,
                "max_results_per_query": 1,
                "max_calls_per_document": 1,
            },
        },
    )
    monkeypatch.setattr(
        fab_tools,
        "_http",
        lambda _url: b"<html><body>" + b"x" * 500 + b" target " + b"y" * 500 + b" target</body></html>",
    )

    matches = fab_tools.search_page_text(
        "https://example.test/filing",
        ["target"],
        context_chars=2_000,
        max_matches=20,
    )

    assert len(matches) == 1
    assert len(matches[0]["snippet"]) < 250
    with pytest.raises(RuntimeError, match="blocks more than 1"):
        fab_tools.search_page_text("https://example.test/filing", ["target"])
    usage = json.loads(ledger.read_text())
    assert usage["calls"]["search_page_text"] == 2
    assert usage["errors"] == 1
    assert list(usage["scoped_calls"]["search_page_text"].values()) == [2]


def test_runtime_policy_rejects_silent_unknown_fields():
    with pytest.raises(ValueError, match="unsupported keys"):
        parse_fab_policy(
            json.dumps(
                {
                    "schema_version": 1,
                    "search_page": {"context_chars": 400, "not_enforced": 3},
                }
            )
        )


def test_runtime_policy_accepts_bounded_machine_tool_output():
    policy = parse_fab_policy(
        json.dumps(
            {
                "schema_version": 1,
                "tool_output": {
                    "enabled": True,
                    "max_chars": 12_000,
                    "tail_chars": 2_000,
                    "tools": ["ipython"],
                },
            }
        )
    )

    assert policy["tool_output"]["max_chars"] == 12_000
    with pytest.raises(ValueError, match="smaller than max_chars"):
        parse_fab_policy(
            json.dumps(
                {
                    "schema_version": 1,
                    "tool_output": {
                        "enabled": True,
                        "max_chars": 2_000,
                        "tail_chars": 2_000,
                        "tools": ["ipython"],
                    },
                }
            )
        )


def test_sec_filings_resolves_ticker_and_returns_direct_documents(tmp_path: Path, monkeypatch):
    ledger = tmp_path / "usage.json"
    monkeypatch.setenv("FAB_TOOLS_USAGE_FILE", str(ledger))
    tickers = {"0": {"cik_str": 1590895, "ticker": "CZR", "title": "Caesars"}}
    submissions = {
        "name": "Caesars Entertainment, Inc.",
        "filings": {
            "recent": {
                "form": ["10-K", "10-Q", "10-K"],
                "filingDate": ["2025-02-25", "2024-11-01", "2024-02-20"],
                "reportDate": ["2024-12-31", "2024-09-30", "2023-12-31"],
                "accessionNumber": ["0001590895-25-000010", "x", "0001590895-24-000010"],
                "primaryDocument": ["czr-20241231.htm", "q3.htm", "czr-20231231.htm"],
            }
        },
    }

    def fake_http(url: str) -> bytes:
        payload = tickers if url == fab_tools.TICKERS_URL else submissions
        return json.dumps(payload).encode()

    monkeypatch.setattr(fab_tools, "_http", fake_http)
    rows = fab_tools.sec_filings(
        "czr",
        form_type="10-K",
        start_date="2024-01-01",
        end_date="2025-12-31",
    )

    assert [row["period_ending"] for row in rows] == ["2024-12-31", "2023-12-31"]
    assert rows[0]["document_url"].endswith("/czr-20241231.htm")
    assert rows[0]["cik"] == "0001590895"
    assert json.loads(ledger.read_text())["calls"] == {"sec_filings": 1}


def test_machine_policy_prefetches_bounded_filing_indices(tmp_path: Path, monkeypatch):
    policy = {
        "schema_version": 1,
        "filing_index": {
            "enabled": True,
            "forms": ["10-K", "8-K"],
            "start_date": "2020-01-01",
            "end_date": "2026-12-31",
            "top_n_per_form": 10,
            "max_tickers": 1,
        },
    }
    (tmp_path / "runtime_policy.json").write_text(json.dumps(policy))
    (tmp_path / "fab_tools.py").write_text("# fixture\n")
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return type("Completed", (), {"returncode": 0, "stdout": "[]", "stderr": ""})()

    monkeypatch.setattr(prime_runner.subprocess, "run", fake_run)
    output = prime_runner._filing_bootstrap(  # noqa: SLF001
        case_root=tmp_path,
        question="Compare NASDAQ:CRWD with NYSE:PANW.",
        env={},
    )

    assert output == tmp_path / "bootstrap_filings.json"
    assert len(calls) == 2
    assert all(command[command.index("--top-n") + 1] == "10" for command in calls)
    assert all("CRWD" in command for command in calls)
    assert {item["form"] for item in json.loads(output.read_text())} == {"10-K", "8-K"}


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


def test_prime_runtime_fails_early_with_provider_diagnostic(tmp_path: Path, monkeypatch):
    fake = tmp_path / "fake_missing_provider.py"
    fake.write_text(
        "import sys\n"
        "sys.stderr.write('OPENAI_BASE_URL is required for the self-harness provider\\n')\n"
        "raise SystemExit(1)\n"
    )
    monkeypatch.setenv(
        "PRIME_AGENT_COMMAND",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(fake))}",
    )

    with pytest.raises(RuntimeError, match="OPENAI_BASE_URL is required"):
        prime_runner.run_question(
            "What is the answer?",
            model="openai/fake",
            log_dir=tmp_path / "artifacts",
            max_turns=5,
            max_time=30,
            max_tokens=1000,
        )


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
    research = json.loads((tmp_path / "artifacts" / "research_result.json").read_text())
    token_flag = research["argv"].index("--autonomous-max-tokens")
    assert research["argv"][token_flag + 1] == "650"
    assert any(item.endswith("/runtime_policy.ts") for item in research["argv"])


def test_prime_runtime_keeps_compiler_text_at_hard_token_boundary(tmp_path: Path, monkeypatch):
    fake = tmp_path / "fake_budgeted_compiler.py"
    fake.write_text(
        """
import json
import sys

is_compiler = '--no-tools' in sys.argv
message = {
    'id': 'compiler' if is_compiler else 'research',
    'role': 'assistant',
    'content': [{'type': 'text', 'text': 'Bounded compiled answer' if is_compiler else 'trace'}],
    'usage': {
        'input': 10,
        'output': 10,
        'totalTokens': 250 if is_compiler else 750,
        'cost': {'total': 0.0},
    },
    'stopReason': 'stop',
}
print(json.dumps({'type': 'message_end', 'message': message}), flush=True)
""".strip()
        + "\n"
    )
    monkeypatch.setenv(
        "PRIME_AGENT_COMMAND",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(fake))}",
    )

    out = prime_runner.run_question(
        "Return a bounded answer",
        model="openai/fake",
        log_dir=tmp_path / "artifacts",
        max_turns=6,
        max_time=30,
        max_tokens=1000,
    )

    compiler = json.loads((tmp_path / "artifacts" / "compiler_result.json").read_text())
    assert compiler["returncode"] == 125
    assert compiler["termination_reason"] == "max_tokens"
    assert out["success"]
    assert out["final_answer"] == "Bounded compiled answer"
    assert out["stop_reason"] == "compiled_after_max_tokens"


def test_prime_runtime_rejects_silent_compiler_as_apparatus_failure(
    tmp_path: Path, monkeypatch
):
    fake = tmp_path / "fake_silent_compiler.py"
    counter = tmp_path / "compiler_calls.txt"
    fake.write_text(
        """
import json
import os
import sys
from pathlib import Path

if '--no-tools' in sys.argv:
    counter = Path(os.environ['FAKE_COMPILER_COUNTER'])
    counter.write_text(counter.read_text() + 'x' if counter.exists() else 'x')
else:
    message = {
        'id': 'research', 'role': 'assistant',
        'content': [{'type': 'text', 'text': 'research only'}],
        'usage': {'totalTokens': 10}, 'stopReason': 'stop',
    }
    print(json.dumps({'type': 'message_end', 'message': message}), flush=True)
""".strip()
        + "\n"
    )
    monkeypatch.setenv("FAKE_COMPILER_COUNTER", str(counter))
    monkeypatch.setenv(
        "PRIME_AGENT_COMMAND",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(fake))}",
    )

    with pytest.raises(RuntimeError, match="no JSON events after 3 attempts"):
        prime_runner.run_question(
            "Return an answer",
            model="openai/fake",
            log_dir=tmp_path / "artifacts",
            max_turns=6,
            max_time=30,
            max_tokens=1000,
        )

    assert counter.read_text() == "xxx"
    assert len(list((tmp_path / "artifacts").glob("compiler_attempt_*.json"))) == 3


def test_strong_harness_has_all_runtime_surfaces():
    strong = ROOT / "benchmarks" / "fabv2" / "harnesses" / "strong"
    prompt = prime_runner.compose_harness_prompt(strong)
    for name in prime_runner.SURFACE_FILES:
        assert (strong / name).exists()
        assert name.removesuffix(".md").title() in prompt
    assert "await rlm(" in (strong / "subagents.md").read_text()
    assert "agent_message.send" in (strong / "subagents.md").read_text()


def test_prime_runtime_locates_only_bundled_agent_message_skill(tmp_path: Path, monkeypatch):
    package = tmp_path / "prime-agent"
    cli = package / "dist" / "bundle" / "cli.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("// fake cli\n")
    cli.chmod(0o755)
    skill = package / "skills" / "agent-message"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: agent-message\n---\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "prime-agent"
    executable.symlink_to(cli)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    assert prime_runner._builtin_agent_message_skill(None) == skill  # noqa: SLF001
