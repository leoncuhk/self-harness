"""Repository-boundary checks for archives and generated content."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
GENERATED_PARTS = {
    ".cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "_runtime",
}


def _tracked_files() -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [Path(line) for line in output.splitlines()]


def test_generated_directories_are_not_tracked() -> None:
    offenders = [
        str(path)
        for path in _tracked_files()
        if GENERATED_PARTS.intersection(path.parts) or path.suffix == ".pyc"
    ]
    assert offenders == []


def test_experiment_configs_cannot_reference_research_archive() -> None:
    offenders = []
    for path in (ROOT / "configs").glob("*.toml"):
        content = path.read_text(encoding="utf-8")
        if "research/" in content or "research\\" in content:
            offenders.append(path.name)
    assert offenders == []


def test_local_documentation_links_resolve() -> None:
    markdown_files = [ROOT / "README.md", *(ROOT / "docs").rglob("*.md")]
    missing = []
    for path in markdown_files:
        content = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            relative_target = target.split("#", maxsplit=1)[0]
            if relative_target and not (path.parent / relative_target).exists():
                missing.append(f"{path.relative_to(ROOT)} -> {target}")
    assert missing == []
