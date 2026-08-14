"""Deterministic coding-agent test double for the dual-loop fixture."""

from __future__ import annotations

import os
from pathlib import Path

product = Path(os.environ["SELF_HARNESS_PRODUCT"])
harness = Path(os.environ["SELF_HARNESS_ROOT"])
policy = (harness / "developer.md").read_text().lower()

# This intentionally models a development harness capability: an agent that is
# told to inspect and run tests discovers the implementation defect; the seed
# policy does not. The real adapter uses the same command contract with Codex or
# Claude Code.
if "test" in policy:
    implementation = product / "calculator.py"
    implementation.write_text(implementation.read_text().replace("a - b", "a + b"))
