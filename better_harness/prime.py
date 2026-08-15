"""Prime Agent subprocess adapter.

Prime is an execution backend, never the authority that accepts a harness.  The
controller gives it a disposable workspace and later evaluates whatever files
it changed with the same frozen runner used for every other proposer.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from better_harness.agent import ProposerWorkspace
    from better_harness.core import Experiment


@dataclass(frozen=True)
class PrimeRunResult:
    """Auditable result of one isolated Prime Agent invocation."""

    argv: tuple[str, ...]
    returncode: int
    duration_s: float
    events: tuple[dict[str, Any], ...]
    stderr: str
    final_text: str
    usage: dict[str, int | float]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the invocation without environment variables or credentials."""
        return {
            "argv": list(self.argv),
            "returncode": self.returncode,
            "duration_s": self.duration_s,
            "events": list(self.events),
            "stderr": self.stderr,
            "final_text": self.final_text,
            "usage": self.usage,
        }


def _command_tokens(raw: object | None) -> list[str]:
    if raw is None:
        return ["prime-agent"]
    if isinstance(raw, str):
        tokens = shlex.split(raw)
    elif isinstance(raw, list):
        tokens = [str(item) for item in raw]
    else:
        raise TypeError("better_agent.command must be a string or list of strings")
    if not tokens:
        raise ValueError("better_agent.command must not be empty")
    return tokens


def _assistant_messages(events: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in events:
        if event.get("type") not in {"message_end", "turn_end", "agent_end"}:
            continue
        candidates: list[object]
        if event.get("type") == "agent_end":
            candidates = list(event.get("messages") or [])
        else:
            candidates = [event.get("message")]
        for candidate in candidates:
            if not isinstance(candidate, dict) or candidate.get("role") != "assistant":
                continue
            identity = str(candidate.get("id") or json.dumps(candidate, sort_keys=True))
            if identity not in seen:
                seen.add(identity)
                messages.append(candidate)
    return messages


def _message_text(message: dict[str, Any]) -> str:
    chunks: list[str] = []
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    for item in content:
        if isinstance(item, str):
            chunks.append(item)
        elif isinstance(item, dict) and item.get("type") == "text":
            chunks.append(str(item.get("text", "")))
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def summarize_prime_events(
    events: tuple[dict[str, Any], ...],
) -> tuple[str, dict[str, int | float]]:
    """Extract final text and de-duplicated root-session model usage."""
    messages = _assistant_messages(events)
    usage: dict[str, int | float] = {
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "total_tokens": 0,
        "cost": 0.0,
    }
    for message in messages:
        raw = message.get("usage") or message.get("usage_metadata") or {}
        input_tokens = int(raw.get("input", raw.get("input_tokens", 0)) or 0)
        output_tokens = int(raw.get("output", raw.get("output_tokens", 0)) or 0)
        cache_read = int(raw.get("cacheRead", raw.get("cache_read_tokens", 0)) or 0)
        cache_write = int(raw.get("cacheWrite", raw.get("cache_write_tokens", 0)) or 0)
        total_tokens = int(
            raw.get(
                "totalTokens",
                raw.get("total", raw.get("total_tokens", input_tokens + output_tokens)),
            )
            or 0
        )
        raw_cost = raw.get("cost") or {}
        cost = float(raw_cost.get("total", 0.0) if isinstance(raw_cost, dict) else 0.0)
        if raw:
            usage["model_calls"] += 1
        usage["input_tokens"] += input_tokens
        usage["output_tokens"] += output_tokens
        usage["cache_read_tokens"] += cache_read
        usage["cache_write_tokens"] += cache_write
        usage["total_tokens"] += total_tokens
        usage["cost"] += cost
    final_text = next((text for text in reversed([_message_text(item) for item in messages]) if text), "")
    return final_text, usage


def run_prime_agent(
    *,
    command: object | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
    cwd: Path,
    timeout_s: float,
    env: dict[str, str] | None = None,
) -> PrimeRunResult:
    """Run one ephemeral, resource-isolated Prime root session in JSON mode."""
    argv = [
        *_command_tokens(command),
        "--mode",
        "json",
        "--no-session",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--offline",
        "--cwd",
        str(cwd),
        "--model",
        model,
        "--thinking",
        "off",
        "--system-prompt",
        system_prompt,
        "--",
        user_prompt,
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=env or os.environ.copy(),
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_s,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Prime Agent executable not found: {_command_tokens(command)[0]!r}; "
            "install Prime Agent or set better_agent.command"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        raw_stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stderr = f"{raw_stderr}\nPrime Agent timed out after {timeout_s}s".strip()

    events: list[dict[str, Any]] = []
    malformed: list[str] = []
    for line in stdout.splitlines():
        try:
            payload = json.loads(line)
        except ValueError:
            if line.strip():
                malformed.append(line)
            continue
        if isinstance(payload, dict):
            events.append(payload)
    if malformed:
        stderr = f"{stderr}\nIgnored {len(malformed)} non-JSON stdout lines".strip()
    event_tuple = tuple(events)
    final_text, usage = summarize_prime_events(event_tuple)
    return PrimeRunResult(
        argv=tuple(argv),
        returncode=returncode,
        duration_s=time.monotonic() - started,
        events=event_tuple,
        stderr=stderr,
        final_text=final_text,
        usage=usage,
    )


def invoke_prime_proposer(*, experiment: Experiment, workspace: ProposerWorkspace) -> str | None:
    """Ask an ephemeral Prime RLM to edit one proposer workspace."""
    from better_harness.agent import DEFAULT_SYSTEM_PROMPT

    config = experiment.better_agent_config
    result = run_prime_agent(
        command=config.get("command"),
        model=experiment.better_agent_model,
        system_prompt=(
            (experiment.better_agent_system_prompt or "").strip()
            + "\n\n"
            + DEFAULT_SYSTEM_PROMPT
            + "\n\nYou are running inside Prime Agent. Use the persistent IPython tool to inspect "
            "and edit files under the current directory. Do not spawn subagents: this experiment "
            "accounts for one proposer root session and requires deterministic isolation."
        ).strip(),
        user_prompt=(
            "Read task.md first. Inspect current/, visible history, and failing train evidence. "
            "Edit only files under current/ and finish by replacing proposal.md with your "
            "evidence, root cause, falsifiable prediction, and concise summary."
        ),
        cwd=workspace.root,
        timeout_s=float(config.get("timeout_s", 900)),
    )
    (workspace.root / "outer_agent_result.json").write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Prime proposer exited {result.returncode}: {result.stderr or 'no stderr'}"
        )
    return result.final_text or None
