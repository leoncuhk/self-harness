"""Prime Agent subprocess adapter.

Prime is an execution backend, never the authority that accepts a harness.  The
controller gives it a disposable workspace and later evaluates whatever files
it changed with the same frozen runner used for every other proposer.
"""

from __future__ import annotations

import json
import os
import queue
import shlex
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DAEMON_SHUTDOWN_SCRIPT = """
const { DaemonClient } = await import(process.argv[1]);
const client = new DaemonClient(process.argv[2]);
await client.connect();
const response = await client.request({type: "shutdown", force: true});
client.close();
if (!response.success) throw new Error(response.error || "daemon shutdown failed");
""".strip()


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
    termination_reason: str | None = None

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
            "termination_reason": self.termination_reason,
        }


def _command_tokens(raw: object | None) -> list[str]:
    if raw is None:
        return ["prime-agent"]
    if isinstance(raw, str):
        tokens = shlex.split(raw)
    elif isinstance(raw, list):
        tokens = [str(item) for item in raw]
    else:
        message = "better_agent.command must be a string or list of strings"
        raise TypeError(message)
    if not tokens:
        message = "better_agent.command must not be empty"
        raise ValueError(message)
    return tokens


def _prime_daemon_client(command: object | None) -> Path | None:
    """Locate Prime's own daemon client for a scoped, protocol-safe shutdown."""
    tokens = _command_tokens(command)
    executable = shutil.which(tokens[0])
    if executable is None:
        return None
    resolved = Path(executable).resolve()
    candidates = [
        resolved.parents[2] / "dist" / "modes" / "daemon" / "daemon-client.js"
    ] if len(resolved.parents) > 2 else []
    return next((path for path in candidates if path.is_file()), None)


def _shutdown_scoped_daemon(command: object | None, socket_path: Path) -> None:
    """Stop the exact per-invocation Prime daemon and remove its short endpoint."""
    if not socket_path.exists():
        return
    client_module = _prime_daemon_client(command)
    node = shutil.which("node")
    if client_module is None or node is None:
        message = f"cannot clean up scoped Prime daemon at {socket_path}"
        raise RuntimeError(message)
    completed = subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            _DAEMON_SHUTDOWN_SCRIPT,
            client_module.as_uri(),
            str(socket_path),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        message = f"failed to stop scoped Prime daemon at {socket_path}: {detail}"
        raise RuntimeError(message)
    endpoint_dir = socket_path.parent
    if endpoint_dir.parent == Path(tempfile.gettempdir()) and endpoint_dir.name.startswith("sh-"):
        shutil.rmtree(endpoint_dir, ignore_errors=True)


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
            identity = str(
                candidate.get("id")
                or candidate.get("timestamp")
                or json.dumps(candidate, sort_keys=True)
            )
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
    if not final_text:
        # A daemon worker can emit a complete streaming text_end and exit zero
        # without the usual message_end envelope. text_end is an explicit model
        # boundary, so it is safe to recover; raw partial deltas are not.
        for event in reversed(events):
            if event.get("type") != "message_update":
                continue
            update = event.get("assistantMessageEvent") or {}
            if isinstance(update, dict) and update.get("type") == "text_end":
                final_text = str(update.get("content") or "").strip()
                if final_text:
                    break
    return final_text, usage


def compact_prime_events(
    events: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    """Remove cumulative streaming snapshots without losing audit boundaries.

    Pi/Prime ``message_update`` events repeat the complete message accumulated so
    far. Persisting every snapshot makes a single response hundreds of megabytes.
    A terminal ``text_end`` is retained for providers that omit ``message_end``;
    ordinary deltas are reconstructable from the final message and are discarded.
    ``turn_end`` and ``agent_end`` are also redundant when explicit message
    boundaries exist.
    """
    has_message_end = any(event.get("type") == "message_end" for event in events)
    compacted: list[dict[str, Any]] = []
    for event in events:
        event_type = event.get("type")
        if event_type == "message_update":
            update = event.get("assistantMessageEvent")
            if isinstance(update, dict) and update.get("type") == "text_end":
                compacted.append({"type": "message_update", "assistantMessageEvent": update})
            continue
        if has_message_end and event_type in {"turn_end", "agent_end"}:
            continue
        compacted.append(event)
    return tuple(compacted)


def _run_json_agent_process(  # noqa: PLR0913 - explicit subprocess contract
    *,
    argv: Sequence[str],
    cwd: Path,
    timeout_s: float,
    env: dict[str, str] | None = None,
    max_turns: int | None = None,
    max_tokens: int | None = None,
) -> PrimeRunResult:
    """Stream one JSON agent process with host-enforced hard budgets."""
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env or os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"agent executable not found: {argv[0]!r}; install the configured runtime or set "
            "better_agent.command"
        ) from exc
    stdout_pipe = process.stdout
    stderr_pipe = process.stderr
    if stdout_pipe is None or stderr_pipe is None:  # pragma: no cover - Popen contract
        message = "agent process pipes were not created"
        raise RuntimeError(message)
    lines: queue.Queue[tuple[str, str | None]] = queue.Queue()

    def pump(label: str, stream: Any) -> None:
        for line in stream:
            lines.put((label, line))
        lines.put((label, None))

    threads = [
        threading.Thread(target=pump, args=("stdout", stdout_pipe), daemon=True),
        threading.Thread(target=pump, args=("stderr", stderr_pipe), daemon=True),
    ]
    for thread in threads:
        thread.start()

    event_list: list[dict[str, Any]] = []
    malformed: list[str] = []
    stderr_lines: list[str] = []
    finished_streams: set[str] = set()
    termination_reason: str | None = None
    deadline = started + timeout_s
    while len(finished_streams) < 2:
        if termination_reason is None and time.monotonic() >= deadline:
            termination_reason = "timeout"
        try:
            label, line = lines.get(timeout=0.1)
        except queue.Empty:
            label, line = "", ""
        if line is None:
            finished_streams.add(label)
            continue
        if label == "stderr":
            stderr_lines.append(line)
        elif label == "stdout" and line:
            try:
                payload = json.loads(line)
            except ValueError:
                if line.strip():
                    malformed.append(line)
            else:
                if isinstance(payload, dict):
                    event_list.append(payload)
                    if payload.get("type") in {"message_end", "turn_end", "agent_end"}:
                        _, live_usage = summarize_prime_events(tuple(event_list))
                        if max_turns is not None and live_usage["model_calls"] >= max_turns:
                            termination_reason = termination_reason or "max_turns"
                        if max_tokens is not None and live_usage["total_tokens"] >= max_tokens:
                            termination_reason = termination_reason or "max_tokens"
        if termination_reason is not None and process.poll() is None:
            stop_signal = signal.SIGTERM if termination_reason == "timeout" else signal.SIGINT
            with suppress(ProcessLookupError, PermissionError):
                os.killpg(process.pid, stop_signal)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    for thread in threads:
        thread.join(timeout=1)

    returncode = process.returncode
    if termination_reason == "timeout":
        returncode = 124
        stderr_lines.append(f"Prime Agent timed out after {timeout_s}s\n")
    elif termination_reason is not None:
        returncode = 125
        stderr_lines.append(f"Prime Agent stopped at hard {termination_reason} budget\n")
    stderr = "".join(stderr_lines)
    if malformed:
        stderr = f"{stderr}\nIgnored {len(malformed)} non-JSON stdout lines".strip()
    raw_events = tuple(event_list)
    final_text, usage = summarize_prime_events(raw_events)
    event_tuple = compact_prime_events(raw_events)
    if final_text and usage["total_tokens"] == 0 and max_tokens is not None:
        # Missing message_end means provider usage is unavailable. Charge the
        # full frozen phase budget rather than reporting a false zero.
        estimated_output = min(max_tokens, max(1, (len(final_text) + 3) // 4))
        usage.update(
            {
                "model_calls": 1,
                "input_tokens": max_tokens - estimated_output,
                "output_tokens": estimated_output,
                "total_tokens": max_tokens,
                "usage_estimated": 1,
            }
        )
    return PrimeRunResult(
        argv=tuple(argv),
        returncode=returncode,
        duration_s=time.monotonic() - started,
        events=event_tuple,
        stderr=stderr,
        final_text=final_text,
        usage=usage,
        termination_reason=termination_reason,
    )


def run_prime_agent(  # noqa: PLR0913 - explicit subprocess contract
    *,
    command: object | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
    cwd: Path,
    timeout_s: float,
    env: dict[str, str] | None = None,
    thinking: str = "off",
    extra_args: Sequence[str] = (),
    input_files: Sequence[Path] = (),
    max_turns: int | None = None,
    max_tokens: int | None = None,
) -> PrimeRunResult:
    """Run one ephemeral Prime root session with host-enforced hard budgets."""
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
        thinking,
        "--system-prompt",
        system_prompt,
        *extra_args,
        *(f"@{path}" for path in input_files),
        "--",
        user_prompt,
    ]
    socket_path: Path | None = None
    if "--daemon-socket" in extra_args:
        index = tuple(extra_args).index("--daemon-socket")
        if index + 1 < len(extra_args):
            socket_path = Path(extra_args[index + 1])
    try:
        return _run_json_agent_process(
            argv=argv,
            cwd=cwd,
            timeout_s=timeout_s,
            env=env,
            max_turns=max_turns,
            max_tokens=max_tokens,
        )
    finally:
        if socket_path is not None:
            _shutdown_scoped_daemon(command, socket_path)


def run_pi_agent(  # noqa: PLR0913 - explicit subprocess contract
    *,
    command: object | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
    cwd: Path,
    timeout_s: float,
    env: dict[str, str] | None = None,
    thinking: str = "off",
    extra_args: Sequence[str] = (),
    input_files: Sequence[Path] = (),
    max_turns: int | None = None,
    max_tokens: int | None = None,
) -> PrimeRunResult:
    """Run one ephemeral Pi session through the same audited process boundary."""
    argv = [
        *_command_tokens(command or "pi"),
        "--mode",
        "json",
        "--no-session",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--offline",
        "--model",
        model,
        "--thinking",
        thinking,
        "--system-prompt",
        system_prompt,
        *extra_args,
        *(f"@{path}" for path in input_files),
        user_prompt,
    ]
    return _run_json_agent_process(
        argv=argv,
        cwd=cwd,
        timeout_s=timeout_s,
        env=env,
        max_turns=max_turns,
        max_tokens=max_tokens,
    )
