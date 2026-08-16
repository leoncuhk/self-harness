"""Frozen, declarative diagnostic contracts for vertical harness domains."""

from __future__ import annotations

import re
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_LAYERS = (
    "beneficiary_capability",
    "data_plane",
    "orchestration",
    "domain_semantics",
    "verification",
    "answer_compilation",
)


@dataclass(frozen=True)
class FacetRule:
    """One deterministic text rule that emits a non-causal routing hint."""

    name: str
    patterns: tuple[str, ...]
    minimum_matches: int = 1

    def __post_init__(self) -> None:
        """Reject ambiguous or invalid declarative rules."""
        if not self.name.strip():
            message = "diagnostic facet name cannot be empty"
            raise ValueError(message)
        if not self.patterns:
            raise ValueError(f"diagnostic facet {self.name!r} needs at least one pattern")
        if not 1 <= self.minimum_matches <= len(self.patterns):
            raise ValueError(
                f"diagnostic facet {self.name!r} minimum_matches must be between 1 and "
                f"{len(self.patterns)}"
            )
        for pattern in self.patterns:
            re.compile(pattern)

    def matches(self, text: str) -> bool:
        """Return whether enough independent patterns match the evidence text."""
        return sum(bool(re.search(pattern, text)) for pattern in self.patterns) >= self.minimum_matches


@dataclass(frozen=True)
class DiagnosticContract:
    """Controller-owned vocabulary and rules for one optimization domain."""

    name: str = "generic-v1"
    layers: tuple[str, ...] = DEFAULT_LAYERS
    guidance: str = (
        "Route the failure before editing. Treat diagnostic facets as observed signals, not "
        "proven causes. Return an empty edit when the evidence points outside the declared "
        "harness surfaces."
    )
    facets: tuple[FacetRule, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Keep the frozen diagnostic vocabulary deterministic."""
        if not self.name.strip():
            message = "diagnostic contract name cannot be empty"
            raise ValueError(message)
        if not self.layers or any(not layer.strip() for layer in self.layers):
            message = "diagnostic contract needs non-empty failure layers"
            raise ValueError(message)
        if len(self.layers) != len(set(self.layers)):
            message = "diagnostic contract failure layers must be unique"
            raise ValueError(message)
        names = [facet.name for facet in self.facets]
        if len(names) != len(set(names)):
            message = "diagnostic facet names must be unique"
            raise ValueError(message)

    def to_dict(self) -> dict[str, Any]:
        """Serialize into manifests and evaluation fingerprints."""
        return asdict(self)

    def render(self) -> str:
        """Render bounded proposer guidance without executable profile code."""
        lines = [
            f"# Diagnostic Contract: {self.name}",
            "",
            "Failure layers:",
            *(f"- `{layer}`" for layer in self.layers),
            "",
            self.guidance.strip(),
            "",
            "Configured diagnostic facets:",
            *(f"- `{facet.name}`" for facet in self.facets),
        ]
        if not self.facets:
            lines.append("- No domain-specific facets; use only generic operational signals.")
        return "\n".join(lines).strip() + "\n"


DEFAULT_DIAGNOSTICS = DiagnosticContract()


@dataclass(frozen=True)
class DiagnosticEvidence:
    """Bounded observations available to deterministic diagnostic rules."""

    stop_reason: str | None = None
    verifier: dict[str, Any] | None = None
    research_tail: str | None = None
    failure_message: str | None = None
    reported_facets: tuple[str, ...] = ()


def load_diagnostic_contract(
    payload: dict[str, Any] | None,
    *,
    config_dir: Path,
) -> DiagnosticContract:
    """Load an inline or file-backed controller diagnostic contract."""
    raw = dict(payload or {})
    if profile_file := raw.pop("profile_file", None):
        if raw:
            message = "diagnostics.profile_file cannot be combined with inline fields"
            raise ValueError(message)
        path = Path(str(profile_file))
        if not path.is_absolute():
            path = (config_dir / path).resolve()
        raw = tomllib.loads(path.read_text())
    facets = tuple(
        FacetRule(
            name=str(item["name"]),
            patterns=tuple(str(pattern) for pattern in item.get("patterns", ())),
            minimum_matches=int(item.get("minimum_matches", 1)),
        )
        for item in raw.pop("facets", ())
    )
    unknown = set(raw) - {"name", "layers", "guidance"}
    if unknown:
        raise ValueError(f"unknown diagnostic contract fields: {sorted(unknown)}")
    return DiagnosticContract(
        name=str(raw.get("name", DEFAULT_DIAGNOSTICS.name)),
        layers=tuple(str(item) for item in raw.get("layers", DEFAULT_DIAGNOSTICS.layers)),
        guidance=str(raw.get("guidance", DEFAULT_DIAGNOSTICS.guidance)),
        facets=facets,
    )


def collect_diagnostic_facets(
    contract: DiagnosticContract,
    evidence: DiagnosticEvidence,
) -> tuple[str, ...]:
    """Combine universal operational signals with domain-declared text rules."""
    text = "\n".join(
        part
        for part in (
            evidence.failure_message,
            evidence.research_tail,
            evidence.stop_reason,
        )
        if part
    ).lower()
    facets = {
        facet
        for facet in evidence.reported_facets
        if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", facet)
    }
    if (evidence.verifier or {}).get("failed_numeric"):
        facets.add("numeric_verifier_miss")
    if evidence.stop_reason and re.search(
        r"(?:max_(?:tokens|turns)|token_limit|turn_limit|exit_125|compiled_after)",
        evidence.stop_reason.lower(),
    ):
        facets.add("budget_boundary")
    if re.search(
        r"permissionerror|operation not permitted|network is unreachable|http 40[133]|http 5\d\d",
        text,
    ):
        facets.add("data_plane_access")
    facets.update(rule.name for rule in contract.facets if rule.matches(text))
    return tuple(sorted(facets))
