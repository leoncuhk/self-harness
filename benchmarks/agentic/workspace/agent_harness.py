"""Frozen inner-agent builder for the agentic suite.

This file is NOT an editable surface. It loads the four editable surfaces
(prompt.txt, tools.py, skills.md, middleware.py) from its own directory at call
time — the eval runner overrides those files per variant — builds a real
deepagents agent over a per-task filesystem sandbox, runs it, and reports token
usage.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent
RECURSION_LIMIT = 60
# One M3 stage makes ~180 inner-agent rollouts, each many API calls, against a
# third-party proxy. Retry coverage previously existed only on the single
# proposer call per iteration, which is why a transient disconnect kept killing
# whole stages.
#
# The budget is stated in wall-clock, not attempts. Two earlier ladders (2s/4s,
# then 5 attempts over ~50s) were each exhausted by a single outage that the
# endpoint recovered from minutes later. Task-level failures are never retried.
MAX_TOTAL_S = 600.0
INITIAL_BACKOFF_S = 5.0
MAX_BACKOFF_S = 60.0
REQUEST_TIMEOUT_S = 120
MODEL_MAX_RETRIES = 3

TRANSIENT_MARKERS = (
    "connection error",
    "server disconnected",
    "remoteprotocolerror",
    "apiconnectionerror",
    "connection reset",
    "connection aborted",
    "temporarily unavailable",
    "timed out",
    "timeout",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
    " 502",
    " 503",
    " 504",
)


def is_transient(error: BaseException) -> bool:
    """Return whether an error is transport noise rather than a task outcome."""
    text = f"{type(error).__name__}: {error}".lower()
    return any(marker in text for marker in TRANSIENT_MARKERS)


def _read_surface(name: str) -> str:
    path = WORKSPACE_ROOT / name
    return path.read_text() if path.exists() else ""


def _load_tools(task_root: str) -> list[Any]:
    source = _read_surface("tools.py")
    if not source.strip():
        return []
    namespace: dict[str, Any] = {}
    exec(compile(source, str(WORKSPACE_ROOT / "tools.py"), "exec"), namespace)  # noqa: S102 - surface is experiment-controlled code
    factory = namespace.get("make_tools")
    return list(factory(task_root)) if callable(factory) else []


def _load_middleware() -> list[Any]:
    source = _read_surface("middleware.py")
    if not source.strip():
        return []
    namespace: dict[str, Any] = {}
    exec(compile(source, str(WORKSPACE_ROOT / "middleware.py"), "exec"), namespace)  # noqa: S102 - surface is experiment-controlled code
    middleware = namespace.get("MIDDLEWARE", [])
    return list(middleware) if isinstance(middleware, (list, tuple)) else []


def _compose_system_prompt() -> str | None:
    prompt = _read_surface("prompt.txt").strip()
    skills = _read_surface("skills.md").strip()
    if not prompt:
        return None  # deepagents stock system prompt (the B5 configuration)
    if skills:
        return prompt + "\n\n# Skills\n\n" + skills
    return prompt


def run_task(*, task_root: str, model: str) -> dict[str, Any]:
    """Run the inner agent once against one task sandbox. Returns usage info.

    Transport failures are retried with the sandbox left untouched between
    attempts, so a retry re-runs the task from its original inputs. Anything
    that is not transport noise propagates on the first attempt and is graded as
    a task failure, which is what keeps a broken harness from looking flaky.
    """
    from deepagents.backends import FilesystemBackend
    from deepagents.graph import create_deep_agent
    from langchain.chat_models import init_chat_model
    from langchain_core.messages import HumanMessage

    model_obj = init_chat_model(
        model,
        temperature=0,
        timeout=REQUEST_TIMEOUT_S,
        max_retries=MODEL_MAX_RETRIES,
    )
    agent = create_deep_agent(
        model=model_obj,
        system_prompt=_compose_system_prompt(),
        tools=_load_tools(task_root),
        middleware=_load_middleware(),
        backend=FilesystemBackend(root_dir=task_root, virtual_mode=True),
    )
    payload = {
        "messages": [
            HumanMessage(
                content=(
                    "Complete the task described in /instructions.txt. All task files "
                    "are under the filesystem root '/'. Read /instructions.txt first, "
                    "then do the work, writing output files exactly where it specifies."
                )
            )
        ]
    }
    attempts_used = 0
    result = None
    started = time.monotonic()
    interval = INITIAL_BACKOFF_S
    while True:
        attempts_used += 1
        try:
            result = agent.invoke(payload, config={"recursion_limit": RECURSION_LIMIT})
            break
        except BaseException as exc:  # noqa: BLE001 - langgraph wraps transport errors in many types
            elapsed = time.monotonic() - started
            if not is_transient(exc) or elapsed + interval > MAX_TOTAL_S:
                raise
            sys.stderr.write(
                f"[retry] inner agent: attempt {attempts_used} failed after "
                f"{elapsed:.0f}s ({type(exc).__name__}); sleeping {interval:.0f}s\n"
            )
            sys.stderr.flush()
            time.sleep(interval)
            interval = min(interval * 2, MAX_BACKOFF_S)
    if result is None:  # pragma: no cover - unreachable: the loop returns or raises
        msg = "inner agent produced no result"
        raise RuntimeError(msg)
    total_tokens = 0
    fingerprints: set[str] = set()
    for message in result.get("messages", []):
        usage = getattr(message, "usage_metadata", None)
        if usage and usage.get("total_tokens"):
            total_tokens += int(usage["total_tokens"])
        metadata = getattr(message, "response_metadata", None)
        if isinstance(metadata, dict) and metadata.get("system_fingerprint"):
            fingerprints.add(str(metadata["system_fingerprint"]))
    return {
        "total_tokens": total_tokens,
        "n_messages": len(result.get("messages", [])),
        "system_fingerprints": sorted(fingerprints),
        "attempts": attempts_used,
    }
