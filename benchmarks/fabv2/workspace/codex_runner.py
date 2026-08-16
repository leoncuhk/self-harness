"""Codex inner-runtime adapter for the FAB v2 evaluator contract."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from harness_runtime import SURFACE_FILES, compose_harness_prompt

from self_harness.codex import CodexRunResult, run_codex_agent

WORKSPACE = Path(__file__).resolve().parent
RUNTIME_FILES = (
    "runtime_policy.json",
    "fab_tools.py",
    "market_data.json",
    "sec_data.json",
)


def _copy_cache(source: Path, target: Path) -> None:
    if not source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        return
    cloned = subprocess.run(
        ["cp", "-cR", str(source), str(target)],
        capture_output=True,
        check=False,
        text=True,
    )
    if cloned.returncode != 0:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)


def _event_counts(result: CodexRunResult) -> tuple[int, int, int]:
    turns = 0
    tool_calls = 0
    errors = int(result.returncode != 0)
    for event in result.events:
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            turns += 1
        if event.get("type") == "item.completed" and item.get("type") == "command_execution":
            tool_calls += 1
            errors += int(item.get("status") == "failed")
    return turns, tool_calls, errors


def _total_tokens(usage: dict[str, int | None]) -> int:
    return sum(int(usage.get(name) or 0) for name in ("input_tokens", "output_tokens"))


def run_question(  # noqa: PLR0913 - evaluator compatibility boundary
    question: str,
    *,
    model: str,
    log_dir: Path,
    max_turns: int,
    max_time: int,
    max_tokens: int,
    prompt_file: Path | None = None,
) -> dict[str, Any]:
    """Run one isolated Codex finance task with the materialized harness."""
    del max_turns, max_tokens, prompt_file  # Codex CLI exposes wall time and model effort here.
    log_dir.mkdir(parents=True, exist_ok=True)
    case_root = log_dir / "codex_workspace"
    if case_root.exists():
        shutil.rmtree(case_root)
    case_root.mkdir(parents=True)
    for name in (*SURFACE_FILES, *RUNTIME_FILES):
        source = WORKSPACE / name
        if source.exists():
            shutil.copy2(source, case_root / name)
    shared_cache = Path(
        os.environ.get(
            "FABV2_CACHE",
            os.environ.get("SELF_HARNESS_SHARED_CACHE", WORKSPACE / ".cache"),
        )
    )
    local_cache = case_root / ".fab-cache"
    _copy_cache(shared_cache, local_cache)

    (case_root / "task.md").write_text(f"# Finance research task\n\n{question.strip()}\n")
    harness = compose_harness_prompt(case_root)
    (case_root / "AGENTS.md").write_text(
        "# Frozen FAB v2 harness\n\nApply these instructions to task.md.\n\n" + harness
    )
    answer_path = case_root / "final_answer.md"
    last_message = log_dir / "last_message.md"
    prompt = (
        "Read task.md and follow AGENTS.md. Solve the finance task using only the supplied task, "
        "harness, fab_tools.py, public sources, and your own calculations. Do not inspect evaluator "
        "code, rubrics, environment variables, sibling directories, the parent repository, or prior "
        f"runs. Use `{sys.executable} {case_root / 'fab_tools.py'} --help` for deterministic tools. "
        "Write the complete standalone answer to final_answer.md before finishing; the file, not a "
        "progress report, is evaluated. Include direct source URLs and all requested calculations."
    )
    env = os.environ.copy()
    usage_path = case_root / "tool_usage.json"
    env["FAB_TOOLS_USAGE_FILE"] = str(usage_path)
    env["FAB_TOOLS_CACHE"] = str(local_cache)
    env["FAB_MARKET_DATA"] = str(case_root / "market_data.json")
    env["FAB_SEC_DATA"] = str(case_root / "sec_data.json")
    result = run_codex_agent(
        command=os.environ.get("CODEX_COMMAND") or None,
        model=model,
        prompt=prompt,
        cwd=case_root,
        output_last_message=last_message,
        timeout_s=max_time,
        reasoning_effort=os.environ.get("CODEX_REASONING_EFFORT", "medium"),
        env=env,
    )
    (log_dir / "codex_run.json").write_text(json.dumps(result.to_dict(), indent=2) + "\n")
    answer = answer_path.read_text().strip() if answer_path.exists() else ""
    if not answer:
        answer = result.final_text
    tool_usage = json.loads(usage_path.read_text()) if usage_path.exists() else {}
    turns, tool_calls, errors = _event_counts(result)
    return {
        "final_answer": answer,
        "tokens": _total_tokens(result.usage),
        "turns": turns,
        "tool_calls_count": tool_calls,
        "error_count": errors + int(tool_usage.get("errors", 0)),
        "tool_usage": tool_usage.get("calls", {}),
        "stop_reason": result.termination_reason
        or ("completed" if result.returncode == 0 else "error"),
        "runtime": "codex-cli",
        "usage": result.usage,
        "duration_s": result.duration_s,
    }
