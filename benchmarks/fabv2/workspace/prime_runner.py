"""Frozen Prime-Agent execution adapter for FAB v2 public development."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

from self_harness.prime import PrimeRunResult, run_prime_agent

WORKSPACE = Path(__file__).resolve().parent
SURFACE_FILES = (
    "system.md",
    "orchestration.md",
    "tools.md",
    "research.md",
    "evidence.md",
    "subagents.md",
    "verification.md",
    "submission.md",
)
RUNTIME_FILES = ("runtime_policy.json", "fab_tools.py", "model_provider.ts")
_TICKER_PATTERN = re.compile(
    r"\b(?:NASDAQ|NYSE)\s*:\s*([A-Z][A-Z0-9.-]{0,9})\b",
    re.IGNORECASE,
)


def compose_harness_prompt(root: Path) -> str:
    """Compose all non-empty declared surfaces in a stable order."""
    parts = []
    for name in SURFACE_FILES:
        path = root / name
        if not path.exists() or not (content := path.read_text().strip()):
            continue
        title = name.removesuffix(".md").replace("_", " ").title()
        parts.append(f"## {title}\n{content}")
    return "\n\n".join(parts).strip() + "\n"


def _command() -> object | None:
    raw = os.environ.get("PRIME_AGENT_COMMAND", "").strip()
    return raw or None


def _builtin_agent_message_skill(command: object | None) -> Path | None:
    """Locate Prime's trusted built-in child-to-parent messaging skill."""
    raw = command or "prime-agent"
    tokens = shlex.split(raw) if isinstance(raw, str) else [str(item) for item in raw]
    if not tokens or not (executable := shutil.which(tokens[0])):
        return None
    resolved = Path(executable).resolve()
    for parent in resolved.parents:
        candidate = parent / "skills" / "agent-message"
        if (candidate / "SKILL.md").is_file():
            return candidate
    return None


def _prime_endpoint(case_root: Path, phase: str) -> tuple[str, Path]:
    """Return short socket/cwd aliases; Prime's Unix endpoints reject long paths."""
    short_root = Path(os.sep) / "tmp"
    directory = Path(tempfile.mkdtemp(prefix="sh-", dir=short_root))
    cwd_alias = directory / "w"
    cwd_alias.symlink_to(case_root, target_is_directory=True)
    return str(directory / f"{phase}.sock"), cwd_alias


def _event_telemetry(result: PrimeRunResult) -> tuple[int, int, dict[str, int]]:
    assistant_ids: set[str] = set()
    errors = 0
    tool_usage: Counter[str] = Counter()
    for event in result.events:
        if event.get("type") == "message_end":
            message = event.get("message") or {}
            if isinstance(message, dict) and message.get("role") == "assistant":
                assistant_ids.add(str(message.get("id") or message.get("timestamp") or id(message)))
                if message.get("stopReason") == "error":
                    errors += 1
        if event.get("type") == "tool_execution_end":
            tool_usage[str(event.get("toolName") or "unknown")] += 1
            errors += int(bool(event.get("isError")))
    return len(assistant_ids), errors, dict(tool_usage)


def _tool_ledger(path: Path) -> tuple[dict[str, int], int]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}, 0
    calls = payload.get("calls") or {}
    return {str(key): int(value) for key, value in calls.items()}, int(payload.get("errors", 0))


def _filing_bootstrap(
    *,
    case_root: Path,
    question: str,
    env: dict[str, str],
) -> Path | None:
    """Execute a bounded declarative filing-index policy before the model runs."""
    policy_path = case_root / "runtime_policy.json"
    if not policy_path.is_file():
        return None
    try:
        policy = json.loads(policy_path.read_text())
    except (OSError, ValueError):
        return None
    filing = policy.get("filing_index") if isinstance(policy, dict) else None
    if not isinstance(filing, dict) or filing.get("enabled") is not True:
        return None
    allowed_forms = {"10-K", "10-Q", "8-K"}
    forms = [str(item) for item in filing.get("forms", []) if str(item) in allowed_forms][:3]
    if not forms:
        return None
    max_tickers = max(1, min(int(filing.get("max_tickers", 4)), 6))
    top_n = max(1, min(int(filing.get("top_n_per_form", 10)), 10))
    tickers = list(dict.fromkeys(match.upper() for match in _TICKER_PATTERN.findall(question)))[
        :max_tickers
    ]
    if not tickers:
        return None
    start_date = str(filing.get("start_date", "2020-01-01"))
    end_date = str(filing.get("end_date", "2026-12-31"))
    records: list[dict[str, Any]] = []
    for ticker in tickers:
        for form in forms:
            command = [
                sys.executable,
                str(case_root / "fab_tools.py"),
                "sec-filings",
                ticker,
                "--form",
                form,
                "--start-date",
                start_date,
                "--end-date",
                end_date,
                "--top-n",
                str(top_n),
            ]
            try:
                completed = subprocess.run(
                    command,
                    cwd=case_root,
                    env=env,
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=45,
                )
            except subprocess.TimeoutExpired:
                records.append({"ticker": ticker, "form": form, "error": "timeout"})
                continue
            if completed.returncode:
                records.append(
                    {
                        "ticker": ticker,
                        "form": form,
                        "error": (completed.stderr or completed.stdout).strip()[:1000],
                    }
                )
                continue
            try:
                filings = json.loads(completed.stdout)
            except ValueError:
                filings = []
            records.append({"ticker": ticker, "form": form, "filings": filings})
    output = case_root / "bootstrap_filings.json"
    output.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
    return output


def _combined_usage(*results: PrimeRunResult) -> dict[str, int | float]:
    keys = {
        "model_calls",
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "total_tokens",
        "cost",
    }
    return {key: sum(result.usage.get(key, 0) for result in results) for key in keys}


def _write_research_trace(result: PrimeRunResult, path: Path) -> None:
    """Persist bounded model/tool evidence even when the model skipped evidence.json."""
    records: list[dict[str, Any]] = []
    for event in result.events:
        event_type = event.get("type")
        if event_type == "tool_execution_end":
            record = {
                "type": "tool",
                "name": event.get("toolName"),
                "arguments": event.get("args"),
                "result": event.get("result"),
                "error": bool(event.get("isError")),
            }
        elif event_type == "message_end":
            message = event.get("message") or {}
            if not isinstance(message, dict) or message.get("role") != "assistant":
                continue
            record = {"type": "assistant", "content": message.get("content")}
        else:
            continue
        encoded = json.dumps(record, ensure_ascii=False, default=str)
        if len(encoded) > 20_000:
            record = {"type": record["type"], "truncated": encoded[:20_000]}
        records.append(record)
    rendered = json.dumps(records, indent=2, ensure_ascii=False, default=str)
    path.write_text(rendered[-120_000:] + "\n")


def run_question(  # noqa: PLR0913 - frozen evaluator contract is intentionally explicit
    question: str,
    *,
    model: str,
    log_dir: Path,
    max_turns: int,
    max_time: int,
    max_tokens: int,
    prompt_file: Path | None = None,
) -> dict[str, Any]:
    """Run one isolated Prime RLM and return answer plus complete accounting."""
    del prompt_file  # compatibility with the prior evaluator call shape
    log_dir.mkdir(parents=True, exist_ok=True)
    case_root = log_dir / "prime_workspace"
    if case_root.exists():
        shutil.rmtree(case_root)
    case_root.mkdir(parents=True)
    for name in (*SURFACE_FILES, *RUNTIME_FILES):
        source = WORKSPACE / name
        if source.exists():
            shutil.copy2(source, case_root / name)

    task = case_root / "task.md"
    task.write_text(f"# Finance research task\n\n{question.strip()}\n")
    answer_path = case_root / "final_answer.md"
    evidence_path = case_root / "evidence.json"
    usage_path = case_root / "tool_usage.json"
    system_prompt = compose_harness_prompt(case_root)
    user_prompt = (
        f"Read {task.name} and solve it. Work only inside {case_root}. "
        f"The hard budget is {max_turns} assistant turns and {max_tokens} cumulative tokens; "
        "finish research and submit before either limit. "
        f"Use {sys.executable} {case_root / 'fab_tools.py'} for deterministic research and "
        "calculation tools; `--help` lists the interface. Maintain evidence.json as directed. "
        f"Your answer is accepted only when you write a complete final response to {answer_path.name}. "
        "Do not inspect evaluator code, rubrics, sibling workspaces, environment variables, or prior cases."
    )
    env = os.environ.copy()
    env["FAB_TOOLS_USAGE_FILE"] = str(usage_path)
    env["FAB_TOOLS_CACHE"] = str(
        Path(
            os.environ.get(
                "FABV2_CACHE",
                os.environ.get("SELF_HARNESS_SHARED_CACHE", WORKSPACE / ".cache"),
            )
        )
    )
    bootstrap_path = _filing_bootstrap(case_root=case_root, question=question, env=env)
    if bootstrap_path is not None:
        user_prompt += (
            f" Read the controller-prepared filing index in {bootstrap_path.name} before doing "
            "open-ended filing search."
        )
    gate = f"test -s {shlex.quote(answer_path.name)}"
    started = time.monotonic()
    research_socket, research_cwd = _prime_endpoint(case_root, "research")
    compiler_reserve = max(1, min(30_000, max_tokens // 4))
    research_token_budget = max(1, max_tokens - compiler_reserve)
    research_turn_budget = max(1, max_turns - 2)
    command = _command()
    agent_message_skill = _builtin_agent_message_skill(command)
    research_result = run_prime_agent(
        command=command,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        cwd=research_cwd,
        timeout_s=max_time + 30,
        env=env,
        thinking=os.environ.get("PRIME_AGENT_THINKING", "off"),
        extra_args=(
            "--daemon-socket",
            research_socket,
            "--extension",
            str(research_cwd / "model_provider.ts"),
            *(("--skill", str(agent_message_skill)) if agent_message_skill else ()),
            "--autonomous",
            "--autonomous-gate",
            gate,
            "--autonomous-gate-retries",
            "2",
            "--autonomous-gate-timeout-ms",
            "10000",
            "--autonomous-max-continuations",
            str(max(1, min(4, research_turn_budget))),
            "--autonomous-max-turns",
            str(research_turn_budget),
            "--autonomous-max-tokens",
            str(research_token_budget),
            "--autonomous-timeout-ms",
            str(max_time * 1000),
        ),
        max_turns=research_turn_budget,
        max_tokens=research_token_budget,
    )
    (log_dir / "research_result.json").write_text(
        json.dumps(research_result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    trace_path = case_root / "research_trace.json"
    _write_research_trace(research_result, trace_path)
    answer = answer_path.read_text().strip() if answer_path.exists() else ""
    compiler_result: PrimeRunResult | None = None
    remaining_tokens = max_tokens - int(research_result.usage.get("total_tokens", 0))
    if not answer and remaining_tokens > 0:
        if research_result.termination_reason is not None:
            time.sleep(3)
        compiler_prompt = "\n\n".join(
            part
            for part in (
                (case_root / "system.md").read_text().strip(),
                (case_root / "verification.md").read_text().strip(),
                (case_root / "submission.md").read_text().strip(),
            )
            if part
        )
        evidence_text = evidence_path.read_text() if evidence_path.exists() else "[]"
        compiler_material = (
            f"HARNESS COMPILATION POLICY:\n{compiler_prompt}\n\nTASK:\n{task.read_text()}"
            f"\n\nSTRUCTURED EVIDENCE:\n{evidence_text[-10_000:]}"
            f"\n\nBOUNDED RESEARCH TRACE:\n{trace_path.read_text()[-50_000:]}"
        )
        compiler_input = case_root / "compiler_input.md"
        compiler_input.write_text(compiler_material)
        compiler_attempts = 3
        for attempt in range(1, compiler_attempts + 1):
            compiler_socket, compiler_cwd = _prime_endpoint(case_root, "compiler")
            compiler_result = run_prime_agent(
                command=command,
                model=model,
                system_prompt=(
                    "You are the frozen answer compiler. Use only the attached task, policy, and "
                    "evidence. Return the complete final answer; do not call tools or describe the process."
                ),
                user_prompt=(
                    "Produce the strongest supported standalone answer, including calculations, "
                    "qualifications, and source URLs present in the attached evidence."
                ),
                cwd=compiler_cwd,
                timeout_s=max(30, min(120, max_time // 3)),
                env=env,
                thinking=os.environ.get("PRIME_AGENT_THINKING", "off"),
                extra_args=(
                    "--daemon-socket",
                    compiler_socket,
                    "--extension",
                    str(compiler_cwd / "model_provider.ts"),
                    "--no-tools",
                ),
                input_files=(compiler_cwd / "compiler_input.md",),
                max_turns=2,
                max_tokens=min(compiler_reserve, remaining_tokens),
            )
            (log_dir / f"compiler_attempt_{attempt}.json").write_text(
                json.dumps(compiler_result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
                + "\n"
            )
            if compiler_result.events or compiler_result.returncode != 0:
                break
            time.sleep(0.5)
        (log_dir / "compiler_result.json").write_text(
            json.dumps(compiler_result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
            + "\n"
        )
        if not compiler_result.events:
            msg = f"Prime compiler produced no JSON events after {compiler_attempts} attempts"
            raise RuntimeError(msg)
        # Prime streams a complete assistant message before the host observes the
        # cumulative-token boundary. Keep that auditable text even when the
        # process is then stopped with return code 125; discarding it turns a
        # bounded, non-empty submission into an apparatus-created zero.
        if compiler_result.final_text.strip():
            answer = compiler_result.final_text.strip()
            answer_path.write_text(answer + "\n")

    results = (research_result,) if compiler_result is None else (research_result, compiler_result)
    usage = _combined_usage(*results)
    (log_dir / "prime_result.json").write_text(
        json.dumps(
            {
                "research": research_result.to_dict(),
                "compiler": None if compiler_result is None else compiler_result.to_dict(),
                "usage": usage,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )
    research_turns, research_errors, builtin_tools = _event_telemetry(research_result)
    compiler_turns = 0
    compiler_errors = 0
    if compiler_result is not None:
        compiler_turns, compiler_errors, _ = _event_telemetry(compiler_result)
    domain_tools, domain_errors = _tool_ledger(usage_path)
    tool_usage = {**builtin_tools, **domain_tools}
    if answer:
        tool_usage["submit_final_result"] = 1
    if compiler_result is not None and answer:
        stop_reason = f"compiled_after_{research_result.termination_reason or 'research'}"
    elif research_result.returncode == 124:
        stop_reason = "timeout"
    elif research_result.returncode:
        stop_reason = f"exit_{research_result.returncode}"
    elif not answer:
        stop_reason = "empty_submission"
    else:
        stop_reason = "submitted"
    return {
        "runtime": "prime-agent",
        "final_answer": answer,
        "success": bool(answer),
        "stop_reason": stop_reason,
        "turns": research_turns + compiler_turns,
        "tokens": int(usage["total_tokens"]),
        "cost": float(usage["cost"]),
        "error_count": research_errors + compiler_errors + domain_errors,
        "tool_calls_count": sum(tool_usage.values()),
        "tool_usage": tool_usage,
        "recovery_used": False,
        "recovery_tokens": 0,
        "recovery_turns": 0,
        "compiler_used": compiler_result is not None,
        "compiler_tokens": (
            0 if compiler_result is None else int(compiler_result.usage.get("total_tokens", 0))
        ),
        "duration_s": round(time.monotonic() - started, 3),
        "evidence_path": str(evidence_path) if evidence_path.exists() else None,
        "usage": usage,
    }
