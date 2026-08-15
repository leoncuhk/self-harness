"""Append-only candidate lineage and anytime-best leaderboard."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class ArchiveEntry:
    """One evaluated harness candidate and its causal lineage."""

    iteration: int
    variant: str
    fingerprint: str
    parent_fingerprint: str | None
    promoted: bool
    changed_surfaces: tuple[str, ...]
    train_passed: int
    train_total: int
    validation_passed: int
    validation_total: int
    train_objective: float
    validation_objective: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize one immutable archive row."""
        return asdict(self)


@dataclass
class CandidateArchive:
    """Run-local archive that preserves accepted and rejected evidence."""

    objective_name: str
    direction: str = "maximize"
    entries: list[ArchiveEntry] = field(default_factory=list)

    def add(self, entry: ArchiveEntry) -> None:
        """Append an entry unless its fingerprint/iteration pair already exists."""
        key = (entry.iteration, entry.fingerprint)
        if any((item.iteration, item.fingerprint) == key for item in self.entries):
            return
        self.entries.append(entry)

    def ranked(self) -> list[ArchiveEntry]:
        """Return candidates ordered by validation then train objective."""
        sign = 1.0 if self.direction == "maximize" else -1.0
        return sorted(
            self.entries,
            key=lambda item: (
                sign * item.validation_objective,
                sign * item.train_objective,
                item.promoted,
                -item.iteration,
            ),
            reverse=True,
        )

    @property
    def anytime_best(self) -> ArchiveEntry | None:
        """Return the best candidate observed so far, promoted or not."""
        ranked = self.ranked()
        return ranked[0] if ranked else None

    def save(self, root: Path) -> None:
        """Write machine-readable lineage and a compact leaderboard."""
        root.mkdir(parents=True, exist_ok=True)
        payload = {
            "objective_name": self.objective_name,
            "direction": self.direction,
            "anytime_best": None if self.anytime_best is None else self.anytime_best.variant,
            "entries": [entry.to_dict() for entry in self.entries],
        }
        (root / "archive.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        lines = [
            "# Candidate leaderboard",
            "",
            f"Objective: `{self.objective_name}` ({self.direction})",
            "",
            "| Rank | Variant | Iter | Promoted | Train | Validation | Surfaces |",
            "| ---: | --- | ---: | --- | ---: | ---: | --- |",
        ]
        for rank, entry in enumerate(self.ranked(), 1):
            lines.append(
                f"| {rank} | `{entry.variant}` | {entry.iteration} | "
                f"{'yes' if entry.promoted else 'no'} | {entry.train_objective:.4f} | "
                f"{entry.validation_objective:.4f} | "
                f"`{', '.join(entry.changed_surfaces) or 'none'}` |"
            )
        (root / "leaderboard.md").write_text("\n".join(lines) + "\n")

    @classmethod
    def load(cls, path: Path) -> CandidateArchive:
        """Reload an archive for resume or analysis."""
        payload = json.loads(path.read_text())
        return cls(
            objective_name=str(payload["objective_name"]),
            direction=str(payload["direction"]),
            entries=[ArchiveEntry(**item) for item in payload.get("entries", ())],
        )


def objective_value(result: Any, name: str) -> float:
    """Read a required objective from a split result."""
    if hasattr(result, "measurable") and not result.measurable:
        msg = (
            f"split {getattr(result, 'split', 'unknown')!r} is unmeasurable: "
            f"{getattr(result, 'apparatus', 0)} apparatus failures and "
            f"{getattr(result, 'total', 0)} measured attempts"
        )
        raise ValueError(msg)
    value = result.metric(name)
    if value is None:
        msg = f"split result did not measure objective {name!r}"
        raise ValueError(msg)
    return float(value)


def baseline_entry(*, variant: Any, train: Any, validation: Any, objective_name: str) -> ArchiveEntry:
    """Build the generation-zero archive row."""
    return ArchiveEntry(
        iteration=0,
        variant=variant.key,
        fingerprint=variant.fingerprint,
        parent_fingerprint=None,
        promoted=True,
        changed_surfaces=variant.changed_surfaces,
        train_passed=train.passed,
        train_total=train.total,
        validation_passed=validation.passed,
        validation_total=validation.total,
        train_objective=objective_value(train, objective_name),
        validation_objective=objective_value(validation, objective_name),
        reason="baseline",
    )


def candidate_entry(  # noqa: PLR0913 - archive rows preserve the full causal comparison
    *,
    iteration: int,
    variant: Any,
    parent_fingerprint: str,
    promoted: bool,
    changed_surfaces: Sequence[str],
    train: Any,
    validation: Any,
    objective_name: str,
    reason: str,
) -> ArchiveEntry:
    """Build one evaluated-candidate archive row."""
    return ArchiveEntry(
        iteration=iteration,
        variant=variant.key,
        fingerprint=variant.fingerprint,
        parent_fingerprint=parent_fingerprint,
        promoted=promoted,
        changed_surfaces=tuple(changed_surfaces),
        train_passed=train.passed,
        train_total=train.total,
        validation_passed=validation.passed,
        validation_total=validation.total,
        train_objective=objective_value(train, objective_name),
        validation_objective=objective_value(validation, objective_name),
        reason=reason,
    )
