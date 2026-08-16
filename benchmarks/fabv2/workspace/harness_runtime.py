"""Runtime-neutral FAB harness composition contract."""

from __future__ import annotations

from pathlib import Path

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
