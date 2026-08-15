"""Atomic Pi adapter for outer harness proposals.

The outer loop is a bounded transformation, not an open-ended coding task.  Pi
therefore receives one controller-built context document, has no tools, and
must return the complete candidate as one JSON value.  The controller validates
and applies that value only after the process exits successfully.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from self_harness.prime import run_pi_agent

if TYPE_CHECKING:
    from self_harness.agent import ProposerWorkspace
    from self_harness.core import Experiment


ATOMIC_SYSTEM_PROMPT = """You propose one harness improvement from bounded evaluation evidence.

Return exactly one JSON object and no markdown. You cannot inspect files or use tools. The supplied
context contains everything you may use. Make one small, general, falsifiable change; do not encode
case answers or evaluator details. `edits` maps declared surface names to their complete replacement
text. Omit unchanged surfaces.

Schema:
{
  "summary": "concise description of the change",
  "root_cause": "causal explanation of the visible failures",
  "evidence": ["specific visible case or normalized-trace facts"],
  "flip_to_pass": ["visible case ids predicted to pass"],
  "at_risk": ["visible case ids that may regress"],
  "edits": {"surface_name": "complete replacement text"}
}

An empty edit set is valid only when the evidence does not justify a change. Never mention or infer
private validation or scorecard content."""


@dataclass(frozen=True)
class AtomicProposal:
    """Validated, all-or-nothing proposal returned by Pi."""

    summary: str
    root_cause: str
    evidence: tuple[str, ...]
    flip_to_pass: tuple[str, ...]
    at_risk: tuple[str, ...]
    edits: dict[str, str]


def build_atomic_context(workspace: ProposerWorkspace) -> str:
    """Serialize only bounded, visible evidence and current editable surfaces."""
    sections = [
        ("TASK", workspace.root / "task.md"),
        ("NORMALIZED EXPERIENCE", workspace.root / "experience" / "records.jsonl"),
        ("FAILURE CLUSTERS", workspace.root / "failure_clusters.json"),
    ]
    chunks = [f"# {title}\n{path.read_text().strip()}" for title, path in sections]
    chunks.append("# CURRENT SURFACES")
    for name, path in sorted(workspace.surface_files.items()):
        chunks.append(f"## {name}\n{path.read_text().strip()}")
    return "\n\n".join(chunks).strip() + "\n"


def parse_atomic_proposal(text: str, *, allowed_surfaces: set[str]) -> AtomicProposal:
    """Parse and validate the single JSON proposal returned by Pi."""
    candidate = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        message = "Pi proposer did not return one valid JSON object"
        raise ValueError(message) from exc
    if not isinstance(payload, dict):
        message = "Pi proposer JSON must be an object"
        raise TypeError(message)

    raw_edits = payload.get("edits", {})
    if not isinstance(raw_edits, dict):
        message = "Pi proposer `edits` must be an object"
        raise TypeError(message)
    unknown = set(raw_edits) - allowed_surfaces
    if unknown:
        raise RuntimeError(f"Pi proposer attempted undeclared surfaces: {sorted(unknown)}")
    edits: dict[str, str] = {}
    for name, value in raw_edits.items():
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"Pi proposer surface {name!r} must be non-empty text")
        edits[str(name)] = value.strip() + "\n"

    def strings(name: str) -> tuple[str, ...]:
        value = payload.get(name, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise TypeError(f"Pi proposer `{name}` must be a string list")
        return tuple(item.strip() for item in value if item.strip())

    summary = payload.get("summary", "")
    root_cause = payload.get("root_cause", "")
    if not isinstance(summary, str) or not isinstance(root_cause, str):
        message = "Pi proposer summary and root_cause must be strings"
        raise TypeError(message)
    return AtomicProposal(
        summary=summary.strip(),
        root_cause=root_cause.strip(),
        evidence=strings("evidence"),
        flip_to_pass=strings("flip_to_pass"),
        at_risk=strings("at_risk"),
        edits=edits,
    )


def _proposal_markdown(proposal: AtomicProposal) -> str:
    prediction: dict[str, Any] = {
        "root_cause": proposal.root_cause,
        "evidence": list(proposal.evidence),
        "flip_to_pass": list(proposal.flip_to_pass),
        "at_risk": list(proposal.at_risk),
    }
    changed = ", ".join(sorted(proposal.edits)) or "none"
    return (
        "# Proposal\n\n"
        f"- Summary: {proposal.summary}\n"
        f"- Surfaces changed: {changed}\n\n"
        "## Prediction\n\n"
        "```json\n"
        f"{json.dumps(prediction, indent=2, ensure_ascii=False)}\n"
        "```\n"
    )


def invoke_pi_proposer(*, experiment: Experiment, workspace: ProposerWorkspace) -> str | None:
    """Generate and atomically apply one bounded Pi proposal."""
    config = experiment.better_agent_config
    context_path = workspace.root / "proposal_context.md"
    context_path.write_text(build_atomic_context(workspace))
    extra_args = ["--no-tools", "--print"]
    extra_args.extend(
        token
        for extension in config.get("extensions", [])
        for token in ("--extension", str(extension))
    )
    result = run_pi_agent(
        command=config.get("command"),
        model=experiment.better_agent_model,
        system_prompt=(
            ((experiment.better_agent_system_prompt or "").strip() + "\n\n")
            + ATOMIC_SYSTEM_PROMPT
        ).strip(),
        user_prompt="Use the attached controller context and return the atomic proposal JSON now.",
        cwd=workspace.root,
        timeout_s=float(config.get("timeout_s", 300)),
        thinking=str(config.get("thinking", "off")),
        extra_args=tuple(extra_args),
        input_files=(context_path,),
        # Pi --print with all tools disabled has exactly one model turn. Passing
        # max_turns=1 to the generic stream monitor would interrupt that turn at
        # its normal message_end before the CLI can exit cleanly.
        max_turns=None,
        max_tokens=int(config.get("max_tokens", 60000)),
    )
    (workspace.root / "outer_agent_result.json").write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"
    )
    if result.returncode != 0:
        raise RuntimeError(f"Pi proposer exited {result.returncode}: {result.stderr or 'no stderr'}")
    proposal = parse_atomic_proposal(
        result.final_text,
        allowed_surfaces=set(workspace.surface_files),
    )
    for name, value in proposal.edits.items():
        workspace.surface_files[name].write_text(value)
    workspace.proposal_file.write_text(_proposal_markdown(proposal))
    return result.final_text or None
