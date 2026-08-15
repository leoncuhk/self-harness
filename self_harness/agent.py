"""Framework-neutral outer proposer and evidence-workspace helpers."""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from self_harness.core import Experiment, Proposal, RunLayout, SplitResult, Variant
from self_harness.ledger import Prediction, parse_prediction
from self_harness.patching import build_variant
from self_harness.signatures import FailureCluster
from self_harness.traces import normalize_outcome, write_experience_bundle


@dataclass(frozen=True)
class ProposerWorkspace:
    """Materialized workspace for one isolated outer proposer."""

    root: Path
    current_dir: Path
    proposal_file: Path
    surface_files: dict[str, Path]


def build_proposer_workspace(  # noqa: PLR0913 - one workspace needs the whole iteration context
    *,
    experiment: Experiment,
    current: Variant,
    train_result: SplitResult,
    layout: RunLayout,
    iteration: int,
    candidate_index: int | None = None,
    clusters: Sequence[FailureCluster] = (),
    total_candidates: int = 1,
) -> ProposerWorkspace:
    """Create one proposer workspace for the current iteration."""
    root = layout.proposer_workspace_dir(iteration, candidate_index)
    if root.exists():
        shutil.rmtree(root)
    current_dir = root / "current"
    current_dir.mkdir(parents=True, exist_ok=True)

    surface_files: dict[str, Path] = {}
    manifest: dict[str, dict[str, str]] = {}
    for name, surface in experiment.surfaces.items():
        path = current_dir / surface.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(current.values[name])
        surface_files[name] = path
        manifest[name] = {
            "kind": surface.kind,
            "target": surface.target,
            "file": str(path.relative_to(root)),
        }

    (root / "surface_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    _write_train_artifacts(
        experiment=experiment,
        train_result=train_result,
        root=root,
    )
    _write_visible_history(layout=layout, root=root)
    (root / "failure_clusters.json").write_text(
        json.dumps([cluster.to_dict() for cluster in clusters], indent=2) + "\n"
    )
    _write_task_file(
        experiment=experiment,
        current=current,
        train_result=train_result,
        root=root,
        clusters=clusters,
        candidate_index=candidate_index,
        total_candidates=total_candidates,
    )
    proposal_file = root / "proposal.md"
    proposal_file.write_text(
        "# Proposal\n\n"
        "- Summary:\n"
        "- Why this should help:\n"
        "- Surfaces changed:\n\n"
        "## Prediction\n\n"
        "Replace this block with your own values. It is graded against the next run.\n\n"
        "```json\n"
        '{\n  "root_cause": "",\n  "evidence": [],\n  "flip_to_pass": [],\n  "at_risk": []\n}\n'
        "```\n"
    )
    return ProposerWorkspace(
        root=root,
        current_dir=current_dir,
        proposal_file=proposal_file,
        surface_files=surface_files,
    )


def load_candidate_values(*, current: Variant, workspace: ProposerWorkspace) -> dict[str, str]:
    """Load surface values back out of one proposer workspace."""
    values = dict(current.values)
    for name, path in workspace.surface_files.items():
        values[name] = path.read_text().strip()
    return values


def read_proposal_summary(workspace: ProposerWorkspace) -> str:
    """Read the proposer summary if present."""
    if not workspace.proposal_file.exists():
        return ""
    return workspace.proposal_file.read_text().strip()


def load_proposal_record(path: Path) -> tuple[Proposal, Variant] | None:
    """Reload a proposal and its candidate variant from a prior run, or None.

    Written by :func:`propose_variant` after every model call. Reloading it on
    resume keeps a restarted iteration byte-identical to the one that crashed —
    without this, a resumed run pays for a fresh proposer call and produces
    different surface values, so no downstream evaluation can be reused either.
    """
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
        proposal_payload = dict(payload["proposal"])
        prediction = Prediction(
            root_cause=str(proposal_payload.get("prediction", {}).get("root_cause", "")),
            evidence=tuple(proposal_payload.get("prediction", {}).get("evidence", ())),
            flip_to_pass=tuple(proposal_payload.get("prediction", {}).get("flip_to_pass", ())),
            at_risk=tuple(proposal_payload.get("prediction", {}).get("at_risk", ())),
        )
        proposal = Proposal(
            changed_surfaces=tuple(proposal_payload["changed_surfaces"]),
            workspace_dir=str(proposal_payload["workspace_dir"]),
            summary=str(proposal_payload["summary"]),
            final_message=proposal_payload.get("final_message"),
            prediction=prediction,
            target_cluster=proposal_payload.get("target_cluster"),
        )
        variant_payload = payload["candidate_variant"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    variant_path = path.parent / "candidate_variant.json"
    variant_path.write_text(json.dumps(variant_payload, indent=2, sort_keys=True) + "\n")
    try:
        candidate = Variant.load(variant_path)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return proposal, candidate


def propose_variant(  # noqa: PLR0913 - one proposal needs the whole iteration context
    *,
    experiment: Experiment,
    current: Variant,
    train_result: SplitResult,
    layout: RunLayout,
    iteration: int,
    candidate_index: int = 0,
    clusters: Sequence[FailureCluster] = (),
    total_candidates: int = 1,
    resume: bool = False,
) -> tuple[Proposal, Variant]:
    """Run the configured outer proposer once and return its candidate variant."""
    scoped_index = candidate_index if total_candidates > 1 else None
    if resume:
        # Check before building the workspace: building it wipes the directory.
        prior = load_proposal_record(
            layout.proposer_workspace_dir(iteration, scoped_index) / "result.json"
        )
        if prior is not None:
            return prior
    workspace = build_proposer_workspace(
        experiment=experiment,
        current=current,
        train_result=train_result,
        layout=layout,
        iteration=iteration,
        candidate_index=scoped_index,
        clusters=clusters,
        total_candidates=total_candidates,
    )
    final_message = invoke_proposer(
        experiment=experiment,
        workspace=workspace,
    )
    values = load_candidate_values(current=current, workspace=workspace)
    changed_surfaces = tuple(
        sorted(name for name in experiment.surfaces if values[name] != current.values[name])
    )
    summary = read_proposal_summary(workspace)
    target_cluster = clusters[candidate_index % len(clusters)].signature.key if clusters else None
    proposal = Proposal(
        changed_surfaces=changed_surfaces,
        workspace_dir=str(workspace.root),
        summary=summary,
        final_message=final_message,
        prediction=parse_prediction(summary, final_message),
        target_cluster=target_cluster,
    )
    label = (
        f"iter-{iteration:03d}"
        if total_candidates <= 1
        else f"iter-{iteration:03d}-k{candidate_index:02d}"
    )
    candidate = build_variant(
        experiment=experiment,
        label=label,
        values=values,
    )
    (workspace.root / "result.json").write_text(
        json.dumps(
            {
                "proposal": proposal.to_dict(),
                "candidate_variant": candidate.to_dict(),
            },
            indent=2,
        )
        + "\n"
    )
    return proposal, candidate


def invoke_proposer(*, experiment: Experiment, workspace: ProposerWorkspace) -> str | None:
    """Dispatch to a framework adapter without moving selection into that framework."""
    if experiment.better_agent_backend == "pi":
        from self_harness.pi import invoke_pi_proposer  # noqa: PLC0415 - circular

        return invoke_pi_proposer(experiment=experiment, workspace=workspace)
    raise ValueError(f"unknown proposer backend {experiment.better_agent_backend!r}")


def _private_case_sources(experiment: Experiment) -> set[str]:
    """Return case source paths that also back a private split.

    Copying train case sources into the proposer workspace is meant to show the
    proposer what the visible tasks ask for. When several cases share one source
    file — the common shape for a parametrised suite, where every task's
    reference implementation sits in one test module — that copy hands over the
    holdout and scorecard verifiers as well. Measured on this repo before the
    fix: ``proposer_workspace/train_cases/tests/test_agentic.py`` contained all
    16 ``verify_*`` implementations, including all four sealed scorecard cases,
    on every iteration.

    A shared source is therefore withheld outright rather than redacted: a
    redaction rule that has to understand the file's structure is a rule that
    can be wrong silently, and being wrong here voids the sealed split.
    """
    private: set[str] = set()
    for split in ("holdout", "scorecard"):
        for case in experiment.cases_for_split(split):
            rendered = case.render(model=experiment.model)
            source = rendered.partition("::")[0] if experiment.runner == "pytest" else rendered
            if source:
                private.add(source)
    return private


def _write_train_artifacts(
    *,
    experiment: Experiment,
    train_result: SplitResult,
    root: Path,
) -> None:
    failures_payload = [
        {
            "case_id": outcome.case_id,
            "stratum": outcome.stratum,
            "status": outcome.status,
            "failure_message": outcome.failure_message,
        }
        for outcome in train_result.failing_outcomes()
    ]
    (root / "train_failures.json").write_text(json.dumps(failures_payload, indent=2) + "\n")
    (root / "train_summary.json").write_text(json.dumps(train_result.to_dict(), indent=2) + "\n")
    write_experience_bundle(root / "experience", train_result.failing_outcomes())

    train_cases_dir = root / "train_cases"
    train_cases_dir.mkdir(parents=True, exist_ok=True)
    withheld: list[str] = []
    private_sources = _private_case_sources(experiment)
    if experiment.runner == "pytest":
        project_root = Path(str(experiment.runner_config["project_root"]))
        copied: set[str] = set()
        for case in experiment.cases_for_split("train"):
            rendered = case.render(model=experiment.model)
            file_part = rendered.partition("::")[0]
            if not file_part or file_part in copied:
                continue
            copied.add(file_part)
            if file_part in private_sources:
                withheld.append(file_part)
                continue
            source = project_root / file_part
            if source.exists():
                target = train_cases_dir / file_part
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    elif experiment.runner == "harbor":
        tasks_root = Path(str(experiment.runner_config["tasks_root"]))
        for case in experiment.cases_for_split("train"):
            rendered = case.render(model=experiment.model)
            if rendered in private_sources:
                withheld.append(rendered)
                continue
            task_dir = tasks_root / rendered
            if task_dir.exists():
                shutil.copytree(task_dir, train_cases_dir / rendered, dirs_exist_ok=True)
    elif experiment.runner == "coding":
        task_root = Path(str(experiment.runner_config["task_root"]))
        for case in experiment.cases_for_split("train"):
            rendered = case.render(model=experiment.model)
            if rendered in private_sources:
                withheld.append(rendered)
                continue
            source = task_root / rendered
            if source.is_file():
                target = train_cases_dir / rendered
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            elif source.is_dir():
                shutil.copytree(source, train_cases_dir / rendered, dirs_exist_ok=True)
    if withheld:
        (train_cases_dir / "WITHHELD.md").write_text(
            "# Withheld case sources\n\n"
            "These train case sources also back holdout or scorecard cases, so copying\n"
            "them here would hand the proposer the private splits' verifiers. Withheld:\n\n"
            + "".join(f"- `{item}`\n" for item in sorted(withheld))
        )


def _write_visible_history(*, layout: RunLayout, root: Path) -> None:
    """Write bounded train-only feedback from earlier candidate attempts."""
    history_dir = root / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[str] = []
    attempts: list[dict[str, object]] = []
    for path in sorted(layout.visible_iterations_dir.rglob("decision.json")):
        payload = json.loads(path.read_text())
        variant = str(payload.get("candidate_variant") or f"iter-{int(payload['iteration']):03d}")
        train_path = layout.visible_root / "train" / variant / "result.json"
        failures: list[dict[str, object]] = []
        train_metrics: dict[str, float] = {}
        if train_path.exists():
            try:
                train = SplitResult.load(train_path)
            except (OSError, ValueError, KeyError, TypeError):
                train = None
            if train is not None:
                train_metrics = train.metrics
                failures = [
                    normalize_outcome(outcome).to_dict()
                    for outcome in train.failing_outcomes()[:4]
                ]
        prediction = payload.get("prediction")
        prediction = prediction if isinstance(prediction, dict) else {}
        changed = [str(item) for item in payload.get("changed_surfaces", ())]
        attempt = {
            "iteration": int(payload["iteration"]),
            "variant": variant,
            "changed_surfaces": changed,
            "train_passed": int(payload.get("train_passed", 0)),
            "train_total": int(payload.get("train_total", 0)),
            "train_metrics": train_metrics,
            "hypothesis": str(prediction.get("root_cause", ""))[:4000],
            "predicted_flips": [str(item) for item in prediction.get("flip_to_pass", ())],
            "train_failures": failures,
        }
        attempts.append(attempt)
        summaries.append(
            f"- Iteration {payload['iteration']}: `{variant}` changed "
            f"`{', '.join(changed) or 'none'}`; visible train "
            f"{payload.get('train_passed', 0)}/{payload.get('train_total', 0)}."
        )
    if not summaries:
        summaries.append("- No previous iterations yet.")
    (history_dir / "visible_history.md").write_text(
        "# Visible History\n\n" + "\n".join(summaries) + "\n"
    )
    (history_dir / "prior_attempts.json").write_text(
        json.dumps(attempts[-5:], indent=2, sort_keys=True, default=str) + "\n"
    )


def _write_task_file(  # noqa: PLR0913 - the task file mirrors the whole iteration context
    *,
    experiment: Experiment,
    current: Variant,
    train_result: SplitResult,
    root: Path,
    clusters: Sequence[FailureCluster] = (),
    candidate_index: int | None = None,
    total_candidates: int = 1,
) -> None:
    cluster_lines = [f"- {cluster.describe()}" for cluster in clusters] or [
        "- No clustered train failures."
    ]
    focus_lines: list[str] = []
    if clusters:
        # Round-robin the candidates across clusters so K proposals attack
        # different root causes instead of restating the same fix K times.
        target = clusters[(candidate_index or 0) % len(clusters)]
        focus_lines = [
            "",
            f"Target this failure cluster: `{target.signature.key}`",
            f"- Cases: {', '.join(target.case_ids)}",
            f"- Mechanism to address: `{target.signature.mechanism}`",
            "- Fix this cluster's root cause. Do not try to fix every cluster at once.",
        ]
    if total_candidates > 1:
        focus_lines += [
            "",
            f"You are candidate {(candidate_index or 0) + 1} of {total_candidates} for this iteration.",
            "Other candidates target other clusters. Your edit must be materially different from",
            "a generic instruction tweak: prefer the mechanism your cluster actually exposes.",
        ]
    surface_lines = [
        f"- `{name}` -> `current/{surface.filename}` ({surface.kind}, target `{surface.target}`)"
        for name, surface in experiment.surfaces.items()
    ]
    failure_lines = [
        f"- `{outcome.case_id}` [{outcome.stratum}]: {outcome.failure_message or outcome.status}"
        for outcome in train_result.failing_outcomes()
    ]
    if not failure_lines:
        failure_lines.append("- No train failures are currently visible.")
    (root / "task.md").write_text(
        "\n".join(
            [
                "# Better Agent Task",
                "",
                "You are improving another agent harness using eval feedback.",
                "",
                "Rules:",
                "- Edit only files under `current/`.",
                "- Do not edit files under `train_cases/`, `history/`, or this task file.",
                "- Prefer general harness improvements over task-specific hacks.",
                "- Do not overfit to the visible examples. Infer the broader policy they suggest and encode that policy into the harness.",
                "- Treat files under `current/` as the real harness surfaces. Write final prompt text, code, or config there.",
                "- For code surfaces such as tools or middleware, write the actual code or registration that should run during eval.",
                "- If you change tool or middleware behavior, update both the implementation and any registration or wiring surfaces you were given.",
                "- Use `surface_manifest.json` to understand how each editable file maps back to the target harness.",
                "- Use the visible train failures and train case files to decide what to change.",
                "- Read `experience/records.jsonl` for bounded execution evidence before diagnosing a failure.",
                "- Keep changes concise and coherent.",
                "- When you finish, update `proposal.md` with a short summary and the prediction JSON block.",
                "- The prediction block is graded against the next run. Predict honestly, not optimistically.",
                "",
                f"Current variant: `{current.key}`",
                f"Current train score: `{train_result.passed}/{train_result.total}` "
                "(counts are attempts across repeats, not cases)",
                *focus_lines,
                "",
                "Editable surfaces:",
                *surface_lines,
                "",
                "Failure clusters (signature `cause|causal_status|mechanism`):",
                *cluster_lines,
                "",
                "Visible train failures:",
                *failure_lines,
                "",
            ]
        )
        + "\n"
    )
