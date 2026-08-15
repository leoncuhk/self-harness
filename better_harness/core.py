"""Core data model, config loading, run loop, history, and CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, replace
from dataclasses import field as dc_field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence

from better_harness.apparatus import (
    STATUS_APPARATUS,
    apparatus_rate,
    is_measurable,
)
from better_harness.archive import CandidateArchive, baseline_entry, candidate_entry
from better_harness.contracts import GoalContract, load_goal_contract
from better_harness.cost import (
    DEFAULT_MAX_COST_GROWTH,
    DEFAULT_MAX_LATENCY_GROWTH,
    DEFAULT_MIN_LATENCY_S,
    CostProfile,
    check_budget,
    profile_split,
)
from better_harness.gate import VALID_GATES, GateDecision, decide
from better_harness.guards import GuardReport, check_variant
from better_harness.ledger import (
    LedgerEntry,
    Prediction,
    compute_flips,
    score_prediction,
    write_ledger,
)
from better_harness.signatures import cluster_split

VALID_SPLITS = ("train", "holdout", "scorecard")
SPLIT_ALIASES = {
    "acceptance": "scorecard",
    "final_eval": "scorecard",
}
VISIBLE_SPLITS = {"train"}
PRIVATE_SPLITS = {"holdout", "scorecard"}
VALID_SURFACE_KINDS = ("module_attr", "workspace_file")
VALID_RUNNERS = ("pytest", "harbor", "coding")
# P0-1: repeat every split this many times unless the config overrides it. One
# rollout per candidate cannot separate a real gain from run-to-run noise.
DEFAULT_REPEATS = 3
# P0-2: Self-Harness promotion rule by default; "combined" reproduces upstream.
DEFAULT_GATE = "conservative"
# P2-5: candidates proposed per iteration. Every extra candidate costs a full
# train+holdout evaluation, so the default stays at 1 and raising it is a
# deliberate spend on proposal diversity.
DEFAULT_CANDIDATES = 1
# A stage that spans two provider fingerprints was not run against one frozen
# model. "strict" fails the stage; "report" records the drift and continues.
DEFAULT_FINGERPRINT_DISCIPLINE = "strict"
VALID_FINGERPRINT_DISCIPLINES = ("strict", "report")
ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")
URL_PATTERN = re.compile(r"https?://[^\s\"'>]+")
UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
)
_EVAL_SOURCE_KEYS = ("project_root", "tasks_root", "task_root", "product_root")
_EVAL_SOURCE_EXCLUDES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "runs",
}


def _source_tree_digest(root: Path) -> str | None:
    """Hash evaluator/task source while excluding generated environments."""
    if not root.exists():
        return None
    paths = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
    digest = hashlib.sha256()
    for path in paths:
        relative = path.name if root.is_file() else str(path.relative_to(root))
        if any(part in _EVAL_SOURCE_EXCLUDES for part in Path(relative).parts):
            continue
        digest.update(relative.encode())
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            return None
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class Surface:
    """One editable harness surface."""

    name: str
    kind: str
    target: str
    base_value: str
    filename: str


@dataclass(frozen=True)
class EvalCase:
    """One explicit eval assignment."""

    case_id: str
    split: str
    stratum: str

    def render(self, *, model: str) -> str:
        """Render one case id for a concrete model."""
        return self.case_id.format(model=model)


@dataclass(frozen=True)
class Experiment:
    """Loaded experiment config."""

    path: Path
    name: str
    runner: str
    workspace_root: Path
    model: str
    max_iterations: int
    better_agent_model: str
    better_agent_max_turns: int
    better_agent_deepagents_root: Path | None
    better_agent_system_prompt: str | None
    runner_config: dict[str, Any]
    surfaces: dict[str, Surface]
    cases: tuple[EvalCase, ...]
    repeats: int = DEFAULT_REPEATS
    gate: str = DEFAULT_GATE
    candidates: int = DEFAULT_CANDIDATES
    guards: dict[str, Any] = dc_field(default_factory=dict)
    budget: dict[str, Any] = dc_field(default_factory=dict)
    fingerprint_discipline: str = DEFAULT_FINGERPRINT_DISCIPLINE
    goal: GoalContract = dc_field(default_factory=GoalContract)

    @property
    def guards_enabled(self) -> bool:
        """Return whether the static edit guard runs."""
        return bool(self.guards.get("enabled", True))

    @property
    def budget_enabled(self) -> bool:
        """Return whether the cost veto runs."""
        return bool(self.budget.get("enabled", True))

    def cases_for_split(self, split: str) -> list[EvalCase]:
        """Return cases for one split."""
        return [case for case in self.cases if case.split == split]

    def rendered_case_ids(self, split: str) -> list[str]:
        """Return rendered case ids for one split."""
        return [case.render(model=self.model) for case in self.cases_for_split(split)]

    def strata_for_split(self, split: str) -> set[str]:
        """Return the stratum set for one split."""
        return {case.stratum for case in self.cases_for_split(split)}

    def has_split(self, split: str) -> bool:
        """Return whether the experiment defines one split."""
        return bool(self.cases_for_split(split))

    @property
    def evaluation_fingerprint(self) -> str:
        """Hash the frozen execution contract that makes a score reusable."""
        source_digests = {
            key: _source_tree_digest(Path(str(self.runner_config[key])))
            for key in _EVAL_SOURCE_KEYS
            if key in self.runner_config
        }
        payload = {
            "schema": 1,
            "runner": self.runner,
            "model": self.model,
            "runner_config": self.runner_config,
            "repeats": self.repeats,
            "cases": [asdict(case) for case in self.cases],
            "source_digests": source_digests,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()


@dataclass(frozen=True)
class Variant:
    """Materialized set of surface values."""

    label: str
    model: str
    changed_surfaces: tuple[str, ...]
    surfaces: dict[str, Surface]
    values: dict[str, str]

    @property
    def key(self) -> str:
        """Return a stable filesystem key."""
        return self.label

    @property
    def fingerprint(self) -> str:
        """Return a content hash over the surface values and model.

        The filesystem key is the *label* (``iter-003``), which is assigned by
        position in the loop and says nothing about content: re-running an
        iteration produces a different harness under the same label. Resume
        therefore has to compare content, not names.
        """
        payload = json.dumps(
            {"model": self.model, "values": self.values},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def attr_overrides(self) -> dict[str, str]:
        """Return module-attr overrides keyed by target."""
        return {
            surface.target: self.values[name]
            for name, surface in self.surfaces.items()
            if surface.kind == "module_attr"
        }

    def file_overrides(self) -> dict[str, str]:
        """Return workspace-file overrides keyed by relative file path."""
        return {
            surface.target: self.values[name]
            for name, surface in self.surfaces.items()
            if surface.kind == "workspace_file"
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the variant."""
        return {
            "label": self.label,
            "model": self.model,
            "changed_surfaces": list(self.changed_surfaces),
            "surfaces": {
                name: asdict(surface)
                for name, surface in self.surfaces.items()
            },
            "values": self.values,
        }

    def save(self, path: Path) -> None:
        """Persist the variant."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")

    @classmethod
    def load(cls, path: Path) -> Variant:
        """Load one variant from disk."""
        payload = json.loads(path.read_text())
        surfaces = {
            name: Surface(**surface_payload)
            for name, surface_payload in payload["surfaces"].items()
        }
        return cls(
            label=str(payload["label"]),
            model=str(payload["model"]),
            changed_surfaces=tuple(str(item) for item in payload["changed_surfaces"]),
            surfaces=surfaces,
            values={name: str(value) for name, value in payload["values"].items()},
        )


@dataclass(frozen=True)
class CaseOutcome:
    """One case-level outcome."""

    case_id: str
    split: str
    stratum: str
    status: str
    score: float
    duration_s: float
    failure_message: str | None = None
    artifacts_dir: str | None = None
    trace_ref: str | None = None
    metrics: dict[str, float] = dc_field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Return whether the outcome counts as passed."""
        return self.status == "passed"

    @property
    def is_apparatus(self) -> bool:
        """Return whether this outcome measured nothing about the harness."""
        return self.status == STATUS_APPARATUS


@dataclass(frozen=True)
class SplitResult:
    """One split result.

    ``passed``/``total`` count only *measured* attempts: apparatus failures are
    excluded from both, and counted separately in ``apparatus``. See
    :mod:`better_harness.apparatus` for why the third class exists.
    """

    split: str
    variant: str
    model: str
    passed: int
    total: int
    score: float
    returncode: int
    run_dir: str
    outcomes: tuple[CaseOutcome, ...]
    apparatus: int = 0
    fingerprints: tuple[str, ...] = ()
    metrics: dict[str, float] = dc_field(default_factory=dict)
    evaluation_fingerprint: str | None = None

    @property
    def correctness(self) -> float:
        """Return pass rate over measured attempts."""
        return 0.0 if self.total == 0 else self.passed / self.total

    @property
    def apparatus_rate(self) -> float:
        """Return apparatus failures as a fraction of attempted evaluations."""
        return apparatus_rate(apparatus=self.apparatus, measured=self.total)

    @property
    def measurable(self) -> bool:
        """Return whether enough of this split ran to support a decision."""
        return is_measurable(apparatus=self.apparatus, measured=self.total)

    def metric(self, name: str) -> float | None:
        """Return a named objective value using stable built-in aliases."""
        builtins = {
            "score": self.score,
            "correctness": self.correctness,
            "passed": float(self.passed),
        }
        return builtins.get(name, self.metrics.get(name))

    def passing_case_ids(self) -> set[str]:
        """Return the set of passed case ids."""
        return {
            outcome.case_id
            for outcome in self.outcomes
            if outcome.passed
        }

    def failing_outcomes(self) -> list[CaseOutcome]:
        """Return failing outcomes that carry evidence about the harness.

        Apparatus failures are excluded: nothing was measured, so mining them for
        harness weaknesses turns infrastructure noise into proposal targets.
        """
        return [
            outcome
            for outcome in self.outcomes
            if outcome.status != "passed" and not outcome.is_apparatus
        ]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result."""
        return {
            "split": self.split,
            "variant": self.variant,
            "model": self.model,
            "passed": self.passed,
            "total": self.total,
            "score": self.score,
            "correctness": self.correctness,
            "apparatus": self.apparatus,
            "apparatus_rate": self.apparatus_rate,
            "measurable": self.measurable,
            "fingerprints": list(self.fingerprints),
            "metrics": self.metrics,
            "evaluation_fingerprint": self.evaluation_fingerprint,
            "returncode": self.returncode,
            "run_dir": self.run_dir,
            "outcomes": [asdict(outcome) for outcome in self.outcomes],
        }

    def save(self, path: Path) -> None:
        """Persist result JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")

    @classmethod
    def load(cls, path: Path) -> SplitResult:
        """Load one split result."""
        payload = json.loads(path.read_text())
        return cls(
            split=str(payload["split"]),
            variant=str(payload["variant"]),
            model=str(payload["model"]),
            passed=int(payload["passed"]),
            total=int(payload["total"]),
            score=float(payload["score"]),
            returncode=int(payload["returncode"]),
            run_dir=str(payload["run_dir"]),
            outcomes=tuple(CaseOutcome(**item) for item in payload["outcomes"]),
            # Absent in results written before the apparatus partition existed.
            apparatus=int(payload.get("apparatus", 0)),
            fingerprints=tuple(str(item) for item in payload.get("fingerprints", ())),
            metrics={str(key): float(value) for key, value in payload.get("metrics", {}).items()},
            evaluation_fingerprint=payload.get("evaluation_fingerprint"),
        )


@dataclass(frozen=True)
class Proposal:
    """One outer-loop Deep Agent proposal."""

    changed_surfaces: tuple[str, ...]
    workspace_dir: str
    summary: str
    final_message: str | None
    prediction: Prediction = dc_field(default_factory=Prediction)
    target_cluster: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the proposal."""
        return asdict(self)


@dataclass(frozen=True)
class CandidateEvaluation:
    """One candidate evaluation."""

    variant: str
    proposal: Proposal
    train: SplitResult
    holdout: SplitResult
    accepted: bool
    reason: str
    gate_decision: GateDecision | None = None
    guard: GuardReport | None = None
    budget: Any | None = None
    cost: tuple[CostProfile, ...] = ()

    def combined_passed(self) -> int:
        """Return the combined pass count."""
        return self.train.passed + self.holdout.passed


@dataclass(frozen=True)
class IterationRecord:
    """One optimization iteration."""

    iteration: int
    starting_variant: str
    candidate: CandidateEvaluation | None


@dataclass(frozen=True)
class RunReport:
    """Final run report."""

    created_at: str
    config_path: str
    model: str
    better_agent_model: str
    baseline: Variant
    final: Variant
    baseline_train: SplitResult
    baseline_holdout: SplitResult
    final_train: SplitResult
    final_holdout: SplitResult
    baseline_scorecard: SplitResult | None
    final_scorecard: SplitResult | None
    iterations: tuple[IterationRecord, ...]
    repeats: int = 1
    gate: str = DEFAULT_GATE

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report."""
        return {
            "created_at": self.created_at,
            "config_path": self.config_path,
            "model": self.model,
            "better_agent_model": self.better_agent_model,
            "repeats": self.repeats,
            "gate": self.gate,
            "baseline": self.baseline.to_dict(),
            "final": self.final.to_dict(),
            "baseline_train": self.baseline_train.to_dict(),
            "baseline_holdout": self.baseline_holdout.to_dict(),
            "final_train": self.final_train.to_dict(),
            "final_holdout": self.final_holdout.to_dict(),
            "baseline_scorecard": None if self.baseline_scorecard is None else self.baseline_scorecard.to_dict(),
            "final_scorecard": None if self.final_scorecard is None else self.final_scorecard.to_dict(),
            "iterations": [
                {
                    "iteration": iteration.iteration,
                    "starting_variant": iteration.starting_variant,
                    "candidate": None
                    if iteration.candidate is None
                    else {
                        "variant": iteration.candidate.variant,
                        "proposal": iteration.candidate.proposal.to_dict(),
                        "accepted": iteration.candidate.accepted,
                        "reason": iteration.candidate.reason,
                        "gate": None
                        if iteration.candidate.gate_decision is None
                        else iteration.candidate.gate_decision.to_dict(),
                        "train": iteration.candidate.train.to_dict(),
                        "holdout": iteration.candidate.holdout.to_dict(),
                    },
                }
                for iteration in self.iterations
            ],
        }

    def to_markdown(self, *, include_scorecard: bool = True) -> str:
        """Render a concise Markdown report.

        ``include_scorecard=False`` withholds the sealed-split row. The file
        written into the run directory always carries it — reading that file is a
        deliberate act — but anything echoed to a terminal or a stage log is not,
        and a scorecard aggregate glimpsed while checking progress spends an
        unseal that a pre-registration only permits once.
        """
        lines = [
            "# better-harness report",
            "",
            f"- Target model: `{self.model}`",
            f"- Better-agent model: `{self.better_agent_model}`",
            f"- Repeats per split: `{self.repeats}`"
            + ("" if self.repeats >= 3 else "  ⚠️ **fewer than 3 repeats: deltas are not separable from noise**"),
            f"- Promotion gate: `{self.gate}`"
            + (
                "  ⚠️ **combined gate allows one split to regress**"
                if self.gate == "combined"
                else ""
            ),
            f"- Baseline changed surfaces: `{', '.join(self.baseline.changed_surfaces) or 'none'}`",
            f"- Final changed surfaces: `{', '.join(self.final.changed_surfaces) or 'none'}`",
            "",
            "| Split | Baseline | Final | Apparatus (baseline / final) |",
            "| --- | --- | --- | --- |",
            (
                f"| Train | `{self.baseline_train.passed}/{self.baseline_train.total}` "
                f"(score {self.baseline_train.score:.4f}) | "
                f"`{self.final_train.passed}/{self.final_train.total}` "
                f"(score {self.final_train.score:.4f}) | "
                f"{_apparatus_cell(self.baseline_train, self.final_train)} |"
            ),
            (
                f"| Validation | `{self.baseline_holdout.passed}/{self.baseline_holdout.total}` "
                f"(score {self.baseline_holdout.score:.4f}) | "
                f"`{self.final_holdout.passed}/{self.final_holdout.total}` "
                f"(score {self.final_holdout.score:.4f}) | "
                f"{_apparatus_cell(self.baseline_holdout, self.final_holdout)} |"
            ),
        ]
        if self.baseline_scorecard is not None and self.final_scorecard is not None:
            lines.append(
                (
                    f"| Locked test | `{self.baseline_scorecard.passed}/{self.baseline_scorecard.total}` "
                    f"(score {self.baseline_scorecard.score:.4f}) | "
                    f"`{self.final_scorecard.passed}/{self.final_scorecard.total}` "
                    f"(score {self.final_scorecard.score:.4f}) | "
                    f"{_apparatus_cell(self.baseline_scorecard, self.final_scorecard)} |"
                )
                if include_scorecard
                else "| Locked test | *sealed* | *sealed* | *sealed* |"
            )
        lines.extend(["", "## Iterations", ""])
        for iteration in self.iterations:
            if iteration.candidate is None:
                lines.append(f"- Iteration {iteration.iteration}: no candidate produced")
                continue
            candidate = iteration.candidate
            decision = "accepted" if candidate.accepted else "rejected"
            lines.extend(
                [
                    f"- Iteration {iteration.iteration}: {decision} `{candidate.variant}`",
                    f"  - Changed surfaces: `{', '.join(candidate.proposal.changed_surfaces) or 'none'}`",
                    f"  - Train: `{candidate.train.passed}/{candidate.train.total}`",
                    f"  - Holdout: `{candidate.holdout.passed}/{candidate.holdout.total}`",
                    f"  - Reason: {candidate.reason}",
                ]
            )
        lines.append("")
        return "\n".join(lines)

    def write(self, output_dir: Path) -> None:
        """Write JSON and Markdown reports."""
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "report.json").write_text(json.dumps(self.to_dict(), indent=2) + "\n")
        (output_dir / "report.md").write_text(self.to_markdown())


class RunLayout:
    """Filesystem layout for one experiment run."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def variants_dir(self) -> Path:
        return self.root / "variants"

    @property
    def visible_root(self) -> Path:
        return self.root / "history" / "visible"

    @property
    def private_root(self) -> Path:
        return self.root / "history" / "private"

    @property
    def visible_iterations_dir(self) -> Path:
        return self.visible_root / "iterations"

    def split_dir(self, *, variant_key: str, split: str) -> Path:
        base = self.visible_root if split in VISIBLE_SPLITS else self.private_root
        return base / split / variant_key

    def variant_path(self, variant_key: str) -> Path:
        return self.variants_dir / f"{variant_key}.json"

    @property
    def runtime_dir(self) -> Path:
        return self.root / "_runtime"

    def proposer_workspace_dir(self, iteration: int, candidate: int | None = None) -> Path:
        base = self.visible_iterations_dir / f"{iteration:03d}" / "proposer_workspace"
        return base if candidate is None else base / f"k{candidate:02d}"

    def iteration_dir(self, iteration: int) -> Path:
        return self.visible_iterations_dir / f"{iteration:03d}"

    def write_manifest(self, experiment: Experiment) -> None:
        """Write experiment metadata and split manifests."""
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "name": experiment.name,
            "runner": experiment.runner,
            "workspace_root": str(experiment.workspace_root),
            "model": experiment.model,
            "max_iterations": experiment.max_iterations,
            "better_agent_model": experiment.better_agent_model,
            "better_agent_max_turns": experiment.better_agent_max_turns,
            "better_agent_deepagents_root": None
            if experiment.better_agent_deepagents_root is None
            else str(experiment.better_agent_deepagents_root),
            "goal": experiment.goal.to_dict(),
        }
        (self.root / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n")
        write_split_manifest(experiment, self.root)

    def write_iteration_decision(
        self,
        *,
        iteration: int,
        starting_variant: str,
        proposal: Proposal,
        candidate: CandidateEvaluation,
        candidate_index: int | None = None,
    ) -> None:
        """Persist one iteration summary."""
        iteration_dir = self.iteration_dir(iteration)
        if candidate_index is not None:
            iteration_dir = iteration_dir / f"k{candidate_index:02d}"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        decision = "accepted" if candidate.accepted else "rejected"
        payload = {
            "iteration": iteration,
            "candidate_index": candidate_index,
            "starting_variant": starting_variant,
            "candidate_variant": candidate.variant,
            "decision": decision,
            "reason": candidate.reason,
            "changed_surfaces": list(proposal.changed_surfaces),
            "train_passed": candidate.train.passed,
            "train_total": candidate.train.total,
            "holdout_passed": candidate.holdout.passed,
            "holdout_total": candidate.holdout.total,
            "gate": None if candidate.gate_decision is None else candidate.gate_decision.to_dict(),
            "guard": None if candidate.guard is None else candidate.guard.to_dict(),
            "budget": None if candidate.budget is None else candidate.budget.to_dict(),
            "cost": [profile.to_dict() for profile in candidate.cost],
            "prediction": proposal.prediction.to_dict(),
            "target_cluster": proposal.target_cluster,
            "summary": proposal.summary,
            "final_message": proposal.final_message,
        }
        (iteration_dir / "decision.json").write_text(json.dumps(payload, indent=2) + "\n")
        lines = [
            f"# Iteration {iteration}",
            "",
            f"- Starting variant: `{starting_variant}`",
            f"- Candidate variant: `{candidate.variant}`",
            f"- Decision: `{decision}`",
            f"- Train: `{candidate.train.passed}/{candidate.train.total}`",
            f"- Holdout: `{candidate.holdout.passed}/{candidate.holdout.total}`",
            f"- Changed surfaces: `{', '.join(proposal.changed_surfaces) or 'none'}`",
            f"- Reason: {candidate.reason}",
            "",
            "## Proposal Summary",
            "",
            proposal.summary or "_No proposal summary written._",
            "",
        ]
        (iteration_dir / "decision.md").write_text("\n".join(lines))

    def write_report(self, report: RunReport) -> None:
        """Write the final report."""
        report.write(self.root)


class FingerprintDriftError(RuntimeError):
    """Raised when one stage spans more than one provider model fingerprint."""


def check_fingerprint_discipline(
    results: Sequence[SplitResult],
    *,
    discipline: str,
) -> tuple[str, ...]:
    """Enforce the pre-registered fingerprint rule and return what was seen.

    The frozen MVP-2 rule reads: *a fingerprint change mid-stage invalidates that
    stage*. It lived in the pre-registration with no code behind it, and it fired
    unnoticed — ``runs/mvp2-evolve`` spans ``fp_e010545658`` (74 rollouts) and
    ``fp_65c6c2730f`` (66) against a single-fingerprint baseline, which under the
    protocol voids the whole evolution stage.

    The weights-frozen premise of self-harness is only as good as the provider's
    routing, so this is not bookkeeping: two fingerprints in one stage means the
    thing being held fixed was not held fixed.
    """
    seen = tuple(sorted({fp for result in results for fp in result.fingerprints}))
    if discipline == "strict" and len(seen) > 1:
        msg = (
            f"fingerprint drift within one stage: {', '.join(seen)}. "
            "The pre-registered rule invalidates a stage whose provider model changed "
            'mid-run; rerun the stage, or set fingerprint_discipline = "report" to '
            "record the drift instead of failing."
        )
        raise FingerprintDriftError(msg)
    return seen


def _apparatus_cell(baseline: SplitResult, final: SplitResult) -> str:
    """Render the apparatus-failure rates for one report row.

    Surfaced next to every score because a split that mostly failed to run and a
    split the agent mostly failed now produce different numbers, and the reader
    has to be able to tell which one they are looking at.
    """
    def one(result: SplitResult) -> str:
        if result.apparatus == 0:
            return "0"
        mark = "" if result.measurable else " ⚠️ **unmeasured**"
        return f"{result.apparatus} ({result.apparatus_rate:.0%}){mark}"

    return f"{one(baseline)} / {one(final)}"


def reusable_result(
    *,
    result_path: Path,
    variant: Variant,
    variant_path: Path,
    evaluation_fingerprint: str | None = None,
) -> SplitResult | None:
    """Return a stored split result, but only if it measured *this* harness.

    Candidate labels are positional (``iter-003``), so a resumed run reaches the
    same directory with different surface values. Reusing on the strength of the
    path alone attributes old numbers to a new candidate — silently, and in the
    direction that looks like a working experiment. Reuse is therefore allowed
    only when the variant JSON stored beside the result still fingerprints
    identically. Anything unreadable or mismatched means re-run.
    """
    if not result_path.exists() or not variant_path.exists():
        return None
    try:
        saved = Variant.load(variant_path)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if saved.fingerprint != variant.fingerprint:
        return None
    try:
        result = SplitResult.load(result_path)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    # An apparatus-heavy result is evidence that measurement failed, not a
    # cached observation of this harness. Resume must retry it after credentials,
    # transport, or host resources are repaired.
    if evaluation_fingerprint is not None and result.evaluation_fingerprint != evaluation_fingerprint:
        return None
    return result if result.measurable else None


def expand_env(value: str) -> str:
    """Expand ${ENV_VAR} references."""
    return ENV_PATTERN.sub(lambda match: os.environ[match.group(1)], value)


def normalize_split(value: str) -> str:
    """Normalize one split name and apply aliases."""
    return SPLIT_ALIASES.get(value, value)


def _resolve_path(config_path: Path, raw: str) -> Path:
    path = Path(expand_env(raw)).expanduser()
    if not path.is_absolute():
        path = (config_path.parent / path).resolve()
    return path


def _resolve_command_tokens(config_path: Path, tokens: list[str]) -> list[str]:
    resolved: list[str] = []
    for token in tokens:
        expanded = expand_env(token)
        candidate = config_path.parent / expanded
        if ("/" in expanded or expanded.endswith(".py")) and candidate.exists():
            resolved.append(str(candidate.resolve()))
        else:
            resolved.append(expanded)
    return resolved


def _surface_filename(
    *,
    name: str,
    target: str,
    base_suffix: str | None,
    kind: str,
    payload: dict,
) -> str:
    if "filename" in payload:
        return str(payload["filename"])
    if kind == "workspace_file":
        return Path(target).name
    suffix = base_suffix or ".txt"
    return f"{name}{suffix}"


def load_experiment(path: str | Path, *, model_override: str | None = None) -> Experiment:
    """Load one experiment config."""
    config_path = Path(path).resolve()
    raw = tomllib.loads(config_path.read_text())
    experiment = raw.get("experiment", {})

    runner = str(experiment.get("runner", "pytest"))
    runner_config = dict(raw.get("runner", {}).get(runner, {}))

    if runner == "pytest" and "evals_project" in experiment and "project_root" not in runner_config:
        runner_config["project_root"] = str(experiment["evals_project"])

    if runner == "pytest":
        runner_config.setdefault("project_root", "libs/evals")
        runner_config.setdefault("pytest_args", ["-q"])
    elif runner == "harbor":
        runner_config.setdefault("tasks_root", "tasks")
        runner_config.setdefault("command", ["harbor"])
        runner_config.setdefault("extra_args", [])
        runner_config.setdefault("pass_threshold", 1.0)
    elif runner == "coding":
        runner_config.setdefault("task_root", "tasks")
        runner_config.setdefault("product_root", "product")
        runner_config.setdefault("ci_commands", [["uv", "run", "pytest", "-q"]])

    if "command" in runner_config:
        runner_config["command"] = _resolve_command_tokens(
            config_path,
            [str(item) for item in runner_config["command"]],
        )

    if "agent_command" in runner_config:
        runner_config["agent_command"] = _resolve_command_tokens(
            config_path,
            [str(item) for item in runner_config["agent_command"]],
        )
    if "ci_commands" in runner_config:
        runner_config["ci_commands"] = [
            _resolve_command_tokens(config_path, [str(item) for item in command])
            for command in runner_config["ci_commands"]
        ]

    for key in ("project_root", "tasks_root", "task_root", "product_root"):
        if key in runner_config:
            runner_config[key] = str(_resolve_path(config_path, str(runner_config[key])))

    name = str(experiment["name"])
    workspace_root = _resolve_path(config_path, str(experiment["workspace_root"]))
    model = model_override or str(experiment.get("model", "default-model"))
    max_iterations = int(experiment.get("max_iterations", 3))
    repeats = int(experiment.get("repeats", DEFAULT_REPEATS))
    gate = str(experiment.get("gate", DEFAULT_GATE))
    candidates = int(experiment.get("candidates", DEFAULT_CANDIDATES))
    fingerprint_discipline = str(
        experiment.get("fingerprint_discipline", DEFAULT_FINGERPRINT_DISCIPLINE)
    )
    guards = dict(raw.get("guards", {}))
    budget = dict(raw.get("budget", {}))
    goal = load_goal_contract(raw.get("goal"))

    better_agent = raw.get("better_agent", {})
    better_agent_model = str(better_agent.get("model", model))
    better_agent_max_turns = int(better_agent.get("max_turns", 11000))
    better_agent_deepagents_root = None
    if raw_root := better_agent.get("deepagents_root"):
        better_agent_deepagents_root = _resolve_path(config_path, str(raw_root))
    elif env_root := os.environ.get("DEEPAGENTS_ROOT"):
        better_agent_deepagents_root = Path(env_root).expanduser().resolve()

    better_agent_system_prompt = None
    if raw_prompt := better_agent.get("system_prompt_file"):
        better_agent_system_prompt = _resolve_path(config_path, str(raw_prompt)).read_text().strip()

    surfaces: dict[str, Surface] = {}
    for surface_name, payload in raw.get("surfaces", {}).items():
        kind = str(payload["kind"])
        target = str(payload["target"])
        has_base_file = "base_file" in payload
        has_base_value = "base_value" in payload
        if has_base_file == has_base_value:
            msg = (
                f"surface '{surface_name}' must define exactly one of "
                "'base_file' or 'base_value'"
            )
            raise ValueError(msg)
        if has_base_file:
            base_file = _resolve_path(config_path, str(payload["base_file"]))
            base_value = base_file.read_text().strip()
            base_suffix = base_file.suffix or ".txt"
        else:
            base_value = str(payload["base_value"]).strip()
            base_suffix = None
        surfaces[surface_name] = Surface(
            name=surface_name,
            kind=kind,
            target=target,
            base_value=base_value,
            filename=_surface_filename(
                name=surface_name,
                target=target,
                base_suffix=base_suffix,
                kind=kind,
                payload=payload,
            ),
        )

    cases = tuple(
        EvalCase(
            case_id=str(item.get("case_id", item.get("nodeid"))),
            split=normalize_split(str(item["split"])),
            stratum=str(item["stratum"]),
        )
        for item in raw.get("cases", [])
    )

    loaded = Experiment(
        path=config_path,
        name=name,
        runner=runner,
        workspace_root=workspace_root,
        model=model,
        max_iterations=max_iterations,
        better_agent_model=better_agent_model,
        better_agent_max_turns=better_agent_max_turns,
        better_agent_deepagents_root=better_agent_deepagents_root,
        better_agent_system_prompt=better_agent_system_prompt,
        runner_config=runner_config,
        surfaces=surfaces,
        cases=cases,
        repeats=repeats,
        gate=gate,
        candidates=candidates,
        guards=guards,
        budget=budget,
        fingerprint_discipline=fingerprint_discipline,
        goal=goal,
    )
    validate_experiment(loaded)
    return loaded


def validate_experiment(experiment: Experiment) -> None:
    """Validate one experiment config."""
    if experiment.runner not in VALID_RUNNERS:
        msg = f"invalid runner {experiment.runner!r}"
        raise ValueError(msg)
    if not experiment.surfaces:
        msg = "config must define at least one surface"
        raise ValueError(msg)
    if experiment.max_iterations < 1:
        msg = "max_iterations must be at least 1"
        raise ValueError(msg)
    if experiment.better_agent_max_turns < 1:
        msg = "better_agent.max_turns must be at least 1"
        raise ValueError(msg)
    if experiment.repeats < 1:
        msg = "repeats must be at least 1"
        raise ValueError(msg)
    if experiment.gate not in VALID_GATES:
        msg = f"invalid gate {experiment.gate!r}; expected one of {VALID_GATES}"
        raise ValueError(msg)
    if experiment.candidates < 1:
        msg = "candidates must be at least 1"
        raise ValueError(msg)
    if experiment.fingerprint_discipline not in VALID_FINGERPRINT_DISCIPLINES:
        msg = (
            f"invalid fingerprint_discipline {experiment.fingerprint_discipline!r}; "
            f"expected one of {VALID_FINGERPRINT_DISCIPLINES}"
        )
        raise ValueError(msg)

    for surface in experiment.surfaces.values():
        if surface.kind not in VALID_SURFACE_KINDS:
            msg = f"invalid surface kind {surface.kind!r}"
            raise ValueError(msg)
        target = Path(surface.target)
        if surface.kind == "workspace_file" and (target.is_absolute() or ".." in target.parts):
            msg = (
                f"workspace surface {surface.name!r} must target a relative path "
                "inside workspace_root"
            )
            raise ValueError(msg)

    splits = {case.split for case in experiment.cases}
    unknown_splits = splits - set(VALID_SPLITS)
    if unknown_splits:
        msg = f"unknown split names: {sorted(unknown_splits)}"
        raise ValueError(msg)

    for split in ("train", "holdout"):
        if not experiment.cases_for_split(split):
            msg = f"split {split!r} must include at least one case"
            raise ValueError(msg)

    rendered = [case.render(model=experiment.model) for case in experiment.cases]
    if len(rendered) != len(set(rendered)):
        msg = "rendered case ids must be unique across all splits"
        raise ValueError(msg)

    if experiment.strata_for_split("train") != experiment.strata_for_split("holdout"):
        msg = (
            "train and holdout must cover the same strata; "
            f"got train={sorted(experiment.strata_for_split('train'))} "
            f"holdout={sorted(experiment.strata_for_split('holdout'))}"
        )
        raise ValueError(msg)

    if experiment.runner == "pytest" and not experiment.runner_config.get("project_root"):
        msg = "pytest runner requires runner.pytest.project_root"
        raise ValueError(msg)
    if experiment.runner == "harbor":
        if not experiment.runner_config.get("tasks_root"):
            msg = "harbor runner requires runner.harbor.tasks_root"
            raise ValueError(msg)
        if not experiment.runner_config.get("command"):
            msg = "harbor runner requires runner.harbor.command"
            raise ValueError(msg)
    if experiment.runner == "coding":
        for key in ("task_root", "product_root", "agent_command", "ci_commands"):
            if not experiment.runner_config.get(key):
                msg = f"coding runner requires runner.coding.{key}"
                raise ValueError(msg)


def write_split_manifest(experiment: Experiment, output_dir: Path) -> None:
    """Write split manifests."""
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        split: [
            {
                "case_id": case.render(model=experiment.model),
                "stratum": case.stratum,
            }
            for case in experiment.cases_for_split(split)
        ]
        for split in VALID_SPLITS
        if experiment.cases_for_split(split)
    }
    (output_dir / "split.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    lines = ["# Split Manifest", ""]
    for split, items in payload.items():
        lines.extend([f"## {split.title()}", ""])
        lines.extend(f"- `{item['stratum']}`: `{item['case_id']}`" for item in items)
        lines.append("")
    (output_dir / "split.md").write_text("\n".join(lines))


def extract_trace_refs(*, payload: Any | None, stdout: str, stderr: str) -> list[str]:
    """Extract URL references from structured payloads and raw logs."""
    urls: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values():
                walk(child)
            return
        if isinstance(value, list):
            for child in value:
                walk(child)
            return
        if isinstance(value, str):
            urls.update(URL_PATTERN.findall(value))

    if payload is not None:
        walk(payload)
    urls.update(URL_PATTERN.findall(stdout))
    urls.update(URL_PATTERN.findall(stderr))
    return sorted(urls)


def write_trace_refs(split_dir: Path, refs: list[str]) -> None:
    """Persist trace references if any were found."""
    if not refs:
        return
    payload = {
        "provider": "langsmith" if any("smith.langchain" in ref for ref in refs) else "generic",
        "urls": refs,
    }
    (split_dir / "trace_refs.json").write_text(json.dumps(payload, indent=2) + "\n")
    lines = ["# Trace References", ""]
    lines.extend(f"- {ref}" for ref in refs)
    lines.append("")
    (split_dir / "trace_refs.md").write_text("\n".join(lines))
    write_trace_payloads(split_dir, refs)


def write_trace_payloads(split_dir: Path, refs: list[str]) -> None:
    """Fetch and persist local copies of LangSmith traces when possible."""
    api_key = os.environ.get("LANGSMITH_API_KEY")
    if not api_key:
        return

    endpoint = (
        os.environ.get("LANGSMITH_ENDPOINT")
        or os.environ.get("LANGCHAIN_ENDPOINT")
        or "https://api.smith.langchain.com"
    ).rstrip("/")
    traces_dir = split_dir / "traces" / "langsmith"
    payloads: list[dict[str, Any]] = []

    for ref in refs:
        trace_id = extract_langsmith_trace_id(ref)
        if trace_id is None:
            continue
        trace_path = traces_dir / f"{trace_id}.json"
        error_text: str | None = None
        if not trace_path.exists():
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                payload = fetch_langsmith_trace(
                    endpoint=endpoint,
                    api_key=api_key,
                    trace_id=trace_id,
                )
            except RuntimeError as exc:
                error_text = str(exc)
            else:
                trace_path.write_text(json.dumps(payload, indent=2) + "\n")
        payloads.append(
            {
                "url": ref,
                "trace_id": trace_id,
                "path": str(trace_path) if trace_path.exists() else None,
                "error": error_text,
            }
        )

    if payloads:
        (split_dir / "trace_payloads.json").write_text(json.dumps(payloads, indent=2) + "\n")


def extract_langsmith_trace_id(url: str) -> str | None:
    """Extract one likely LangSmith run id from a URL."""
    if "smith.langchain" not in url:
        return None
    matches = UUID_PATTERN.findall(url)
    if not matches:
        return None
    return matches[-1]


def fetch_langsmith_trace(*, endpoint: str, api_key: str, trace_id: str) -> dict[str, Any]:
    """Fetch one LangSmith run with messages included."""
    base_url = f"{endpoint}/runs/{trace_id}?include_messages=true"
    if not base_url.startswith(("https://", "http://")):
        msg = f"Unsupported LangSmith endpoint: {endpoint}"
        raise RuntimeError(msg)
    request = urllib.request.Request(  # noqa: S310
        base_url,
        headers={
            "X-API-Key": api_key,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LangSmith fetch failed for {trace_id}: HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LangSmith fetch failed for {trace_id}: {exc}") from exc


def collect_trace_refs(run_dir: Path) -> list[dict[str, Any]]:
    """Collect all saved trace reference files under one run."""
    collected: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("trace_refs.json")):
        payload = json.loads(path.read_text())
        collected.append(
            {
                "path": str(path),
                "provider": payload.get("provider", "generic"),
                "urls": payload.get("urls", []),
            }
        )
    return collected


def run_experiment(
    experiment: Experiment,
    *,
    output_dir: Path,
    max_iterations: int | None = None,
    reuse_existing: bool = False,
) -> RunReport:
    """Run the better-harness optimization loop."""
    from better_harness.agent import propose_variant
    from better_harness.patching import build_baseline_variant
    from better_harness.repeats import run_split_repeated
    from better_harness.runners import build_runner

    runner = build_runner(experiment)
    layout = RunLayout(output_dir.resolve())
    layout.write_manifest(experiment)

    iteration_limit = experiment.max_iterations if max_iterations is None else max_iterations
    baseline = build_baseline_variant(experiment)
    current = baseline
    baseline_train = run_split_repeated(
        runner,
        experiment=experiment,
        variant=baseline,
        split="train",
        layout=layout,
        reuse_existing=reuse_existing,
    )
    baseline_holdout = run_split_repeated(
        runner,
        experiment=experiment,
        variant=baseline,
        split="holdout",
        layout=layout,
        reuse_existing=reuse_existing,
    )
    current_train = baseline_train
    current_holdout = baseline_holdout
    archive = CandidateArchive(
        objective_name=experiment.goal.primary_metric,
        direction=experiment.goal.direction,
    )
    archive.add(
        baseline_entry(
            variant=baseline,
            train=baseline_train,
            validation=baseline_holdout,
            objective_name=experiment.goal.primary_metric,
        )
    )
    archive.save(layout.root / "archive")
    # Fail fast rather than at the end: a stage that has already drifted cannot
    # be salvaged by finishing it, and every further rollout is spend on a stage
    # the protocol will void.
    stage_results: list[SplitResult] = [baseline_train, baseline_holdout]
    check_fingerprint_discipline(stage_results, discipline=experiment.fingerprint_discipline)

    iterations: list[IterationRecord] = []
    ledger: list[LedgerEntry] = []
    for index in range(1, iteration_limit + 1):
        if current_train.passed == current_train.total and current_holdout.passed == current_holdout.total:
            break
        clusters = cluster_split(current_train)
        current_cost = [profile_split(current_train), profile_split(current_holdout)]

        evaluated: list[tuple[CandidateEvaluation, Variant, SplitResult, SplitResult]] = []
        proposed_any = False
        for candidate_index in range(experiment.candidates):
            proposal, candidate_variant = propose_variant(
                experiment=experiment,
                current=current,
                train_result=current_train,
                layout=layout,
                iteration=index,
                candidate_index=candidate_index,
                clusters=clusters,
                total_candidates=experiment.candidates,
                resume=reuse_existing,
            )
            if not proposal.changed_surfaces:
                continue
            proposed_any = True

            guard_report: GuardReport | None = None
            if experiment.guards_enabled:
                guard_report = check_variant(
                    experiment=experiment,
                    baseline=baseline,
                    candidate=candidate_variant,
                    forbidden_patterns=experiment.guards.get("forbidden_patterns"),
                    max_growth=experiment.guards.get("max_growth"),
                    min_bloat_bytes=experiment.guards.get("min_bloat_bytes"),
                )
                if not guard_report.ok:
                    # Rejected statically: never spend an evaluation on it.
                    evaluated.append(
                        (
                            CandidateEvaluation(
                                variant=candidate_variant.key,
                                proposal=proposal,
                                train=current_train,
                                holdout=current_holdout,
                                accepted=False,
                                reason=guard_report.reason(),
                                guard=guard_report,
                            ),
                            candidate_variant,
                            current_train,
                            current_holdout,
                        )
                    )
                    continue

            train = run_split_repeated(
                runner,
                experiment=experiment,
                variant=candidate_variant,
                split="train",
                layout=layout,
                reuse_existing=reuse_existing,
            )
            holdout = run_split_repeated(
                runner,
                experiment=experiment,
                variant=candidate_variant,
                split="holdout",
                layout=layout,
                reuse_existing=reuse_existing,
            )
            stage_results.extend([train, holdout])
            check_fingerprint_discipline(stage_results, discipline=experiment.fingerprint_discipline)
            gate_decision = decide(
                gate=experiment.gate,
                goal=experiment.goal,
                current_train=current_train,
                current_holdout=current_holdout,
                candidate_train=train,
                candidate_holdout=holdout,
            )
            candidate_cost = [profile_split(train), profile_split(holdout)]
            budget_decision = None
            accepted = gate_decision.accepted
            reason = gate_decision.reason
            if accepted and experiment.budget_enabled:
                budget_decision = check_budget(
                    current=current_cost,
                    candidate=candidate_cost,
                    max_cost_growth=float(
                        experiment.budget.get("max_cost_growth", DEFAULT_MAX_COST_GROWTH)
                    ),
                    max_latency_growth=float(
                        experiment.budget.get("max_latency_growth", DEFAULT_MAX_LATENCY_GROWTH)
                    ),
                    min_latency_s=float(
                        experiment.budget.get("min_latency_s", DEFAULT_MIN_LATENCY_S)
                    ),
                )
                if not budget_decision.within_budget:
                    # Correctness improved but it was bought, not earned.
                    accepted = False
                    reason = f"{gate_decision.reason} | {budget_decision.reason}"

            evaluated.append(
                (
                    CandidateEvaluation(
                        variant=candidate_variant.key,
                        proposal=proposal,
                        train=train,
                        holdout=holdout,
                        accepted=accepted,
                        reason=reason,
                        gate_decision=gate_decision,
                        guard=guard_report,
                        budget=budget_decision,
                        cost=tuple(candidate_cost),
                    ),
                    candidate_variant,
                    train,
                    holdout,
                )
            )

        if not proposed_any:
            iterations.append(
                IterationRecord(
                    iteration=index,
                    starting_variant=current.key,
                    candidate=None,
                )
            )
            break

        winner = _select_winner(evaluated)
        parent_fingerprint = current.fingerprint
        for position, (candidate, _candidate_variant, train, holdout) in enumerate(evaluated):
            is_winner = winner is not None and position == winner
            ledger.append(
                _build_ledger_entry(
                    iteration=index,
                    candidate=candidate,
                    promoted=is_winner,
                    clusters=clusters,
                    current_train=current_train,
                    current_holdout=current_holdout,
                    train=train,
                    holdout=holdout,
                )
            )
            layout.write_iteration_decision(
                iteration=index,
                starting_variant=current.key,
                proposal=candidate.proposal,
                candidate=candidate,
                candidate_index=position if experiment.candidates > 1 else None,
            )
            iterations.append(
                IterationRecord(
                    iteration=index,
                    starting_variant=current.key,
                    candidate=candidate,
                )
            )
            archive.add(
                candidate_entry(
                    iteration=index,
                    variant=_candidate_variant,
                    parent_fingerprint=parent_fingerprint,
                    promoted=is_winner,
                    changed_surfaces=candidate.proposal.changed_surfaces,
                    train=train,
                    validation=holdout,
                    objective_name=experiment.goal.primary_metric,
                    reason=candidate.reason,
                )
            )

        archive.save(layout.root / "archive")

        if winner is not None:
            _, current, current_train, current_holdout = evaluated[winner]

    write_ledger(layout.root / "ledger.json", ledger)

    baseline_scorecard = _run_optional_scorecard(
        experiment=experiment,
        runner=runner,
        variant=baseline,
        layout=layout,
        reuse_existing=reuse_existing,
    )
    if current.fingerprint == baseline.fingerprint:
        # Nothing was promoted, so the "final" harness *is* the baseline. Running
        # the sealed split a second time would spend another full evaluation and
        # — because both runs key on the same variant label — overwrite the first
        # one's artifacts in place. That is how every recorded final_scorecard in
        # this repo came to read 0/20 against true scores of 17-18/20: the second
        # write landed, and it was the one that hit the parse defect.
        final_scorecard = baseline_scorecard
    else:
        final_scorecard = _run_optional_scorecard(
            experiment=experiment,
            runner=runner,
            variant=current,
            layout=layout,
            reuse_existing=reuse_existing,
        )

    report = RunReport(
        created_at=datetime.now(tz=UTC).isoformat(timespec="seconds"),
        config_path=str(experiment.path),
        model=experiment.model,
        better_agent_model=experiment.better_agent_model,
        baseline=baseline,
        final=current,
        baseline_train=baseline_train,
        baseline_holdout=baseline_holdout,
        final_train=current_train,
        final_holdout=current_holdout,
        baseline_scorecard=baseline_scorecard,
        final_scorecard=final_scorecard,
        iterations=tuple(iterations),
        repeats=experiment.repeats,
        gate=experiment.gate,
    )
    layout.write_report(report)
    return report


def _select_winner(
    evaluated: list[tuple[CandidateEvaluation, Any, SplitResult, SplitResult]],
) -> int | None:
    """Pick which accepted candidate to promote.

    Among candidates that cleared the gate and the cost veto, prefer the largest
    holdout gain and use the train gain only to break ties. Holdout is the split
    the proposer could not read, so it is the better estimate of which edit
    actually generalizes.
    """
    best: int | None = None
    best_key: tuple[float, float, float, float] | None = None
    for position, (candidate, _variant, _train, _holdout) in enumerate(evaluated):
        if not candidate.accepted or candidate.gate_decision is None:
            continue
        key = (
            candidate.gate_decision.delta_ho_score,
            candidate.gate_decision.delta_in_score,
            float(candidate.gate_decision.delta_ho),
            float(candidate.gate_decision.delta_in),
        )
        if best_key is None or key > best_key:
            best_key = key
            best = position
    return best


def _build_ledger_entry(  # noqa: PLR0913 - a ledger row records the full iteration context
    *,
    iteration: int,
    candidate: CandidateEvaluation,
    promoted: bool,
    clusters: list[Any],
    current_train: SplitResult,
    current_holdout: SplitResult,
    train: SplitResult,
    holdout: SplitResult,
) -> LedgerEntry:
    """Grade one candidate's prediction against the flips it actually caused."""
    flips = compute_flips(
        current=[current_train, current_holdout],
        candidate=[train, holdout],
    )
    prediction = candidate.proposal.prediction
    return LedgerEntry(
        iteration=iteration,
        variant=candidate.variant,
        accepted=promoted,
        gate_reason=candidate.reason,
        changed_surfaces=candidate.proposal.changed_surfaces,
        prediction=prediction,
        flips=flips,
        score=score_prediction(prediction, flips),
        guard=None if candidate.guard is None else candidate.guard.to_dict(),
        budget=None if candidate.budget is None else candidate.budget.to_dict(),
        signature_clusters=[cluster.to_dict() for cluster in clusters],
    )


def _run_optional_scorecard(
    *,
    experiment: Experiment,
    runner,
    variant,
    layout: RunLayout,
    reuse_existing: bool,
) -> SplitResult | None:
    from better_harness.repeats import run_split_repeated

    if not experiment.has_split("scorecard"):
        return None
    return run_split_repeated(
        runner,
        experiment=experiment,
        variant=variant,
        split="scorecard",
        layout=layout,
        reuse_existing=reuse_existing,
    )


def inventory_payload(experiment: Experiment) -> dict[str, object]:
    """Build one JSON-serializable inventory payload."""
    from better_harness.runners import build_runner

    runner = build_runner(experiment)
    return {
        "name": experiment.name,
        "runner": experiment.runner,
        "workspace_root": str(experiment.workspace_root),
        "model": experiment.model,
        "cases": runner.collect_inventory(experiment),
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="Improve an agent harness with a Deep Agent outer loop")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate one experiment config")
    validate_parser.add_argument("config", type=Path)
    validate_parser.add_argument("--model")

    inventory_parser = subparsers.add_parser("inventory", help="List available eval units")
    inventory_parser.add_argument("config", type=Path)
    inventory_parser.add_argument("--model")
    inventory_parser.add_argument("--output", type=Path)

    split_parser = subparsers.add_parser("split", help="Write the configured split manifest")
    split_parser.add_argument("config", type=Path)
    split_parser.add_argument("--model")
    split_parser.add_argument("--output-dir", type=Path, default=Path("split"))

    run_parser = subparsers.add_parser("run", help="Run the outer Deep Agent optimization loop")
    run_parser.add_argument("config", type=Path)
    run_parser.add_argument("--model")
    run_parser.add_argument("--max-iterations", type=int)
    run_parser.add_argument(
        "--reuse-existing",
        "--resume",
        dest="reuse_existing",
        action="store_true",
        help=(
            "reuse prior proposals and split results from --output-dir when they "
            "provably measured the same harness (variant fingerprint match)"
        ),
    )
    run_parser.add_argument("--output-dir", type=Path)
    run_parser.add_argument(
        "--show-scorecard",
        action="store_true",
        help=(
            "print the sealed scorecard row to stdout. Off by default so stage "
            "logs cannot spend a pre-registered unseal by accident"
        ),
    )
    run_parser.add_argument(
        "--repeats",
        type=int,
        help=f"rollouts per split per candidate (config default: {DEFAULT_REPEATS})",
    )
    run_parser.add_argument(
        "--gate",
        choices=VALID_GATES,
        help=f"promotion gate (config default: {DEFAULT_GATE})",
    )

    inspect_parser = subparsers.add_parser("inspect", help="Summarize one run directory")
    inspect_parser.add_argument("run_dir", type=Path)

    traces_parser = subparsers.add_parser("traces", help="List saved local and LangSmith trace refs")
    traces_parser.add_argument("run_dir", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "inspect":
        report_path = args.run_dir / "report.json"
        payload = json.loads(report_path.read_text())
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "traces":
        refs = collect_trace_refs(args.run_dir)
        print(json.dumps({"count": len(refs), "items": refs}, indent=2))
        return 0

    experiment = load_experiment(args.config, model_override=getattr(args, "model", None))
    overrides = {
        field: value
        for field, value in (("repeats", getattr(args, "repeats", None)), ("gate", getattr(args, "gate", None)))
        if value is not None
    }
    if overrides:
        experiment = replace(experiment, **overrides)
        validate_experiment(experiment)

    if args.command == "validate":
        print(f"Config valid: {experiment.path}")
        print(f"Runner: {experiment.runner}")
        print(f"Workspace: {experiment.workspace_root}")
        print(f"Model: {experiment.model}")
        print(f"Better-agent model: {experiment.better_agent_model}")
        print(f"Repeats per split: {experiment.repeats}")
        print(f"Promotion gate: {experiment.gate}")
        print(f"Surfaces: {', '.join(experiment.surfaces)}")
        print(f"Train: {len(experiment.cases_for_split('train'))} cases")
        print(f"Holdout: {len(experiment.cases_for_split('holdout'))} cases")
        print(f"Scorecard: {len(experiment.cases_for_split('scorecard'))} cases")
        return 0

    if args.command == "inventory":
        payload = inventory_payload(experiment)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(payload, indent=2) + "\n")
            print(args.output)
        else:
            print(json.dumps(payload, indent=2))
        return 0

    if args.command == "split":
        output_dir = args.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        write_split_manifest(experiment, output_dir)
        print(output_dir / "split.json")
        return 0

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or Path("runs") / f"{experiment.name}-{timestamp}"
    report = run_experiment(
        experiment,
        output_dir=output_dir,
        max_iterations=args.max_iterations,
        reuse_existing=args.reuse_existing,
    )
    print(report.to_markdown(include_scorecard=args.show_scorecard))
    if not args.show_scorecard and report.final_scorecard is not None:
        print("\n> Scorecard withheld from stdout. Unseal deliberately: `--show-scorecard`, or read report.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
