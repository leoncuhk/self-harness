"""Pi coding-agent adapter for bounded outer harness proposals."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from better_harness.prime import build_proposer_prompts, run_pi_agent

if TYPE_CHECKING:
    from better_harness.agent import ProposerWorkspace
    from better_harness.core import Experiment


def invoke_pi_proposer(*, experiment: Experiment, workspace: ProposerWorkspace) -> str | None:
    """Ask one ephemeral Pi session to edit a proposer workspace."""
    config = experiment.better_agent_config
    system_prompt, user_prompt = build_proposer_prompts(experiment, runtime_name="Pi Agent")
    extra_args = tuple(
        token
        for extension in config.get("extensions", [])
        for token in ("--extension", str(extension))
    )
    result = run_pi_agent(
        command=config.get("command"),
        model=experiment.better_agent_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        cwd=workspace.root,
        timeout_s=float(config.get("timeout_s", 900)),
        thinking=str(config.get("thinking", "off")),
        extra_args=extra_args,
        max_turns=experiment.better_agent_max_turns,
        max_tokens=(
            int(config["max_tokens"]) if config.get("max_tokens") is not None else None
        ),
    )
    (workspace.root / "outer_agent_result.json").write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"
    )
    if result.returncode != 0:
        raise RuntimeError(f"Pi proposer exited {result.returncode}: {result.stderr or 'no stderr'}")
    return result.final_text or None
