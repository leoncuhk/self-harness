from __future__ import annotations

import json
import sys
import textwrap
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
    assert _command_tokens("uv run --project '/opt/prime source' prime-agent") == [
        "uv",
        "run",
        "--project",
        "/opt/prime source",
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


def test_run_prime_agent_builds_isolated_json_command(tmp_path: Path):
    fake = tmp_path / "fake.py"
    fake.write_text(
        textwrap.dedent(
            """
            import json
            import os
            import sys
            from pathlib import Path

            Path("captured.json").write_text(json.dumps({"argv": sys.argv[1:], "env": os.getenv("TEST_ONLY")}))
            message = {
                "id": "m1", "role": "assistant",
                "content": [{"type": "text", "text": "finished"}],
                "usage": {"input": 8, "output": 2, "cacheRead": 3, "cacheWrite": 4,
                          "totalTokens": 17, "cost": {"total": 0.0125}},
            }
            print(json.dumps({"type": "message_end", "message": message}), flush=True)
            """
        ).strip()
        + "\n"
    )
    result = run_prime_agent(
        command=[sys.executable, str(fake)],
        model="openai/test-model",
        system_prompt="frozen prompt",
        user_prompt="do the task",
        cwd=tmp_path,
        timeout_s=30,
        env={"TEST_ONLY": "1"},
        thinking="high",
        extra_args=("--autonomous", "--autonomous-max-turns", "7"),
        input_files=(tmp_path / "context.md",),
    )

    captured = json.loads((tmp_path / "captured.json").read_text())
    argv = captured["argv"]
    assert argv[:2] == ["--mode", "json"]
    assert "--no-session" in argv
    assert "--no-context-files" in argv
    assert argv[argv.index("--thinking") + 1] == "high"
    assert "--autonomous" in argv
    assert f"@{tmp_path / 'context.md'}" in argv
    assert argv[-2:] == ["--", "do the task"]
    assert captured["env"] == "1"
    assert result.final_text == "finished"
    assert result.usage["total_tokens"] == 17


def test_run_prime_agent_records_timeout_as_failed_result(tmp_path: Path):
    fake = tmp_path / "sleep.py"
    fake.write_text("import time\ntime.sleep(10)\n")
    result = run_prime_agent(
        command=[sys.executable, str(fake)],
        model="openai/test-model",
        system_prompt="prompt",
        user_prompt="task",
        cwd=tmp_path,
        timeout_s=0.1,
    )
    assert result.returncode == 124
    assert "timed out" in result.stderr


def test_run_prime_agent_enforces_streaming_token_budget(tmp_path: Path):
    fake = tmp_path / "many.py"
    fake.write_text(
        textwrap.dedent(
            """
            import json
            import time
            for index in range(100):
                message = {
                    "id": f"m{index}", "role": "assistant", "content": [],
                    "usage": {"input": 60, "output": 10, "totalTokens": 70},
                }
                print(json.dumps({"type": "message_end", "message": message}), flush=True)
                time.sleep(0.02)
            """
        ).strip()
        + "\n"
    )
    result = run_prime_agent(
        command=[sys.executable, str(fake)],
        model="openai/test-model",
        system_prompt="prompt",
        user_prompt="task",
        cwd=tmp_path,
        timeout_s=5,
        max_tokens=200,
    )
    assert result.returncode == 125
    assert result.termination_reason == "max_tokens"
    assert 200 <= result.usage["total_tokens"] < 500


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
