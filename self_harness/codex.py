"""Auditable OpenAI Codex CLI execution adapter.

Codex is an execution backend, not an evaluation or promotion authority. The
controller owns the workspace, prompt, model, budget, and acceptance decision.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CodexRunResult:
    """Complete, credential-free record of one Codex CLI invocation."""

    argv: tuple[str, ...]
    returncode: int
    duration_s: float
    events: tuple[dict[str, Any], ...]
    stderr: str
    final_text: str
    usage: dict[str, int | None]
    termination_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the invocation without its environment."""
        return {
            "argv": list(self.argv),
            "returncode": self.returncode,
            "duration_s": self.duration_s,
            "events": list(self.events),
            "stderr": self.stderr,
            "final_text": self.final_text,
            "usage": self.usage,
            "termination_reason": self.termination_reason,
        }


def _command_tokens(raw: object | None) -> list[str]:
    if raw is None:
        return ["codex"]
    if isinstance(raw, str):
        tokens = shlex.split(raw)
    elif isinstance(raw, list | tuple):
        tokens = [str(item) for item in raw]
    else:
        message = "Codex command must be a string or sequence"
        raise TypeError(message)
    if not tokens:
        message = "Codex command must not be empty"
        raise ValueError(message)
    return tokens


def _events(stdout: str) -> tuple[dict[str, Any], ...]:
    parsed: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            parsed.append(event)
    return tuple(parsed)


def _usage(events: tuple[dict[str, Any], ...]) -> dict[str, int | None]:
    for event in reversed(events):
        usage = event.get("usage")
        if isinstance(usage, dict):
            return {
                "input_tokens": usage.get("input_tokens"),
                "cached_input_tokens": usage.get("cached_input_tokens"),
                "output_tokens": usage.get("output_tokens"),
            }
    return {"input_tokens": None, "cached_input_tokens": None, "output_tokens": None}


def run_codex_agent(  # noqa: PLR0913 - explicit fields define the frozen invocation
    *,
    model: str,
    prompt: str,
    cwd: Path,
    output_last_message: Path,
    timeout_s: int,
    reasoning_effort: str = "medium",
    command: object | None = None,
    env: dict[str, str] | None = None,
    sandbox: str = "workspace-write",
) -> CodexRunResult:
    """Run one ephemeral Codex process and retain its JSON event stream."""
    argv = [
        *_command_tokens(command),
        "exec",
        "--model",
        model,
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-rules",
        "--sandbox",
        sandbox,
        "--config",
        f'model_reasoning_effort="{reasoning_effort}"',
        "--json",
        "--output-last-message",
        str(output_last_message),
        "--cd",
        str(cwd),
        prompt,
    ]
    started = time.monotonic()
    termination_reason = None
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=os.environ.copy() if env is None else env,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_s,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        raw_stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stderr = f"{raw_stderr}\nCodex timed out after {timeout_s}s".strip()
        termination_reason = "timeout"
    duration_s = time.monotonic() - started
    events = _events(stdout)
    final_text = output_last_message.read_text().strip() if output_last_message.exists() else ""
    return CodexRunResult(
        argv=tuple(argv),
        returncode=returncode,
        duration_s=duration_s,
        events=events,
        stderr=stderr,
        final_text=final_text,
        usage=_usage(events),
        termination_reason=termination_reason,
    )
