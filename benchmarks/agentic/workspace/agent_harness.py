"""Frozen inner-agent builder for the agentic suite.

This file is NOT an editable surface. It loads the four editable surfaces
(prompt.txt, tools.py, skills.md, middleware.py) from its own directory at call
time — the eval runner overrides those files per variant — builds a real
deepagents agent over a per-task filesystem sandbox, runs it, and reports token
usage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parent
RECURSION_LIMIT = 60


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
    """Run the inner agent once against one task sandbox. Returns usage info."""
    from deepagents.backends import FilesystemBackend
    from deepagents.graph import create_deep_agent
    from langchain.chat_models import init_chat_model
    from langchain_core.messages import HumanMessage

    model_obj = init_chat_model(model, temperature=0)
    agent = create_deep_agent(
        model=model_obj,
        system_prompt=_compose_system_prompt(),
        tools=_load_tools(task_root),
        middleware=_load_middleware(),
        backend=FilesystemBackend(root_dir=task_root, virtual_mode=True),
    )
    result = agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "Complete the task described in /instructions.txt. All task files "
                        "are under the filesystem root '/'. Read /instructions.txt first, "
                        "then do the work, writing output files exactly where it specifies."
                    )
                )
            ]
        },
        config={"recursion_limit": RECURSION_LIMIT},
    )
    total_tokens = 0
    for message in result.get("messages", []):
        usage = getattr(message, "usage_metadata", None)
        if usage and usage.get("total_tokens"):
            total_tokens += int(usage["total_tokens"])
    return {"total_tokens": total_tokens, "n_messages": len(result.get("messages", []))}
