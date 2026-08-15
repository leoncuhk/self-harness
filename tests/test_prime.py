from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from better_harness.prime import _command_tokens, run_prime_agent, summarize_prime_events


def _assistant(message_id: str, text: str, *, input_tokens: int, output_tokens: int):
    return {
        "id": message_id,
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "usage": {
            "input": input_tokens,
            "output": output_tokens,
            "cacheRead": 3,
            "cacheWrite": 4,
            "totalTokens": input_tokens + output_tokens + 7,
            "cost": {"total": 0.0125},
        },
    }


def test_command_tokens_accepts_quoted_command_and_rejects_empty():
    assert _command_tokens("uv run --project '/tmp/prime source' prime-agent") == [
        "uv",
        "run",
        "--project",
        "/tmp/prime source",
        "prime-agent",
    ]
    with pytest.raises(ValueError, match="must not be empty"):
        _command_tokens([])
    with pytest.raises(TypeError, match="string or list"):
        _command_tokens(7)


def test_summarize_events_deduplicates_messages_and_counts_child_attribution():
    first = _assistant("m1", "working", input_tokens=10, output_tokens=2)
    final = _assistant("m2", "done", input_tokens=20, output_tokens=5)
    # Prime repeats the same message in message_end, turn_end, and agent_end.
    events = (
        {"type": "message_end", "message": first},
        {"type": "turn_end", "message": first},
        {"type": "message_end", "message": final},
        {"type": "agent_end", "messages": [first, final]},
    )
    text, usage = summarize_prime_events(events)
    assert text == "done"
    assert usage == {
        "model_calls": 2,
        "input_tokens": 30,
        "output_tokens": 7,
        "cache_read_tokens": 6,
        "cache_write_tokens": 8,
        "total_tokens": 51,
        "cost": 0.025,
    }


def test_run_prime_agent_builds_isolated_json_command(tmp_path: Path, monkeypatch):
    message = _assistant("m1", "finished", input_tokens=8, output_tokens=2)
    captured: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        captured.update(argv=argv, **kwargs)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps({"type": "message_end", "message": message}) + "\n",
            stderr="",
        )

    monkeypatch.setattr("better_harness.prime.subprocess.run", fake_run)
    result = run_prime_agent(
        command=["prime-agent"],
        model="openai/test-model",
        system_prompt="frozen prompt",
        user_prompt="do the task",
        cwd=tmp_path,
        timeout_s=30,
        env={"TEST_ONLY": "1"},
    )

    argv = captured["argv"]
    assert isinstance(argv, list)
    assert argv[:3] == ["prime-agent", "--mode", "json"]
    assert "--no-session" in argv
    assert "--no-context-files" in argv
    assert argv[-2:] == ["--", "do the task"]
    assert captured["cwd"] == tmp_path
    assert captured["env"] == {"TEST_ONLY": "1"}
    assert result.final_text == "finished"
    assert result.usage["total_tokens"] == 17


def test_run_prime_agent_records_timeout_as_failed_result(tmp_path: Path, monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("prime-agent", 1, output=b"", stderr=b"partial")

    monkeypatch.setattr("better_harness.prime.subprocess.run", fake_run)
    result = run_prime_agent(
        command=None,
        model="openai/test-model",
        system_prompt="prompt",
        user_prompt="task",
        cwd=tmp_path,
        timeout_s=1,
    )
    assert result.returncode == 124
    assert "timed out" in result.stderr


def test_run_prime_agent_explains_missing_executable(tmp_path: Path):
    with pytest.raises(RuntimeError, match="executable not found"):
        run_prime_agent(
            command=[str(tmp_path / "missing-prime")],
            model="openai/test-model",
            system_prompt="prompt",
            user_prompt="task",
            cwd=tmp_path,
            timeout_s=1,
        )
