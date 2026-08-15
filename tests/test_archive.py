from __future__ import annotations

from pathlib import Path

from self_harness.archive import ArchiveEntry, CandidateArchive


def entry(name: str, *, validation: float, iteration: int, promoted: bool = False) -> ArchiveEntry:
    return ArchiveEntry(
        iteration=iteration,
        variant=name,
        fingerprint=f"fp-{name}",
        parent_fingerprint=None,
        promoted=promoted,
        changed_surfaces=("prompt",),
        train_passed=1,
        train_total=2,
        validation_passed=1,
        validation_total=2,
        train_objective=validation,
        validation_objective=validation,
        reason="test",
    )


def test_archive_keeps_rejected_anytime_best_and_lineage(tmp_path: Path):
    archive = CandidateArchive(objective_name="score")
    archive.add(entry("baseline", validation=0.2, iteration=0, promoted=True))
    archive.add(entry("candidate", validation=0.8, iteration=1))
    archive.save(tmp_path)
    assert archive.anytime_best is not None
    assert archive.anytime_best.variant == "candidate"
    assert "candidate" in (tmp_path / "leaderboard.md").read_text()
    loaded = CandidateArchive.load(tmp_path / "archive.json")
    assert len(loaded.entries) == 2


def test_archive_deduplicates_resume_rows():
    archive = CandidateArchive(objective_name="score")
    row = entry("candidate", validation=0.8, iteration=1)
    archive.add(row)
    archive.add(row)
    assert archive.entries == [row]
