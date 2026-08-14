"""Pytest and Harbor eval runners."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence

from better_harness.apparatus import STATUS_APPARATUS, apparatus_kind
from better_harness.coding import CodingProjectRunner
from better_harness.core import (
    CaseOutcome,
    EvalCase,
    Experiment,
    RunLayout,
    SplitResult,
    Variant,
    extract_trace_refs,
    reusable_result,
    write_trace_refs,
)
from better_harness.patching import (
    VARIANT_ENV,
    ensure_sitecustomize,
    prepend_pythonpath,
    workspace_override_context,
)


class PytestRunner:
    """Run explicit pytest subsets against one variant."""

    def __init__(self, *, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parents[1]

    def collect_inventory(self, experiment: Experiment) -> list[str]:
        """Collect pytest nodeids."""
        project_root = Path(str(experiment.runner_config["project_root"]))
        command = self._base_command(experiment)
        command.extend(["--collect-only"])
        command.extend(str(arg) for arg in experiment.runner_config.get("pytest_args", ["-q"]))
        env = os.environ.copy()
        runtime_dir = ensure_sitecustomize(self.repo_root / ".runtime")
        env["PYTHONPATH"] = prepend_pythonpath(
            [runtime_dir, self.repo_root, experiment.workspace_root],
            env.get("PYTHONPATH"),
        )
        completed = subprocess.run(
            command,
            cwd=project_root,
            env=env,
            capture_output=True,
            check=False,
            text=True,
        )
        if completed.returncode != 0:
            msg = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"pytest collection failed: {msg}")
        return [
            line.strip()
            for line in completed.stdout.splitlines()
            if "::" in line and line.strip()
        ]

    def run_split(
        self,
        *,
        experiment: Experiment,
        variant: Variant,
        split: str,
        layout: RunLayout,
        reuse_existing: bool = False,
    ) -> SplitResult:
        """Run one split and capture artifacts."""
        split_dir = layout.split_dir(variant_key=variant.key, split=split)
        result_path = split_dir / "result.json"
        variant_path = layout.variant_path(variant.key)
        if reuse_existing:
            reused = reusable_result(
                result_path=result_path,
                variant=variant,
                variant_path=variant_path,
            )
            if reused is not None:
                return reused

        split_dir.mkdir(parents=True, exist_ok=True)
        variant.save(variant_path)
        project_root = Path(str(experiment.runner_config["project_root"]))
        env = self._build_env(
            experiment=experiment,
            variant_path=variant_path,
            runtime_dir=ensure_sitecustomize(layout.runtime_dir),
        )

        outcomes: list[CaseOutcome] = []
        returncodes: list[int] = []
        split_stdout: list[str] = []
        split_stderr: list[str] = []
        fingerprints: set[str] = set()

        with workspace_override_context(experiment.workspace_root, variant.file_overrides()):
            for case in experiment.cases_for_split(split):
                rendered = case.render(model=experiment.model)
                case_slug = safe_slug(rendered)
                case_dir = split_dir / "cases" / case_slug
                case_dir.mkdir(parents=True, exist_ok=True)
                summary_path = case_dir / "summary.json"
                junit_path = case_dir / "junit.xml"
                # Clear the artifact paths before invoking pytest. pytest treats
                # every non-option argv token as a possible path and keeps the
                # ones that *already exist* when computing rootdir
                # (_pytest/config/findpaths.py: `if safe_exists(path)`). The
                # values of --junitxml and --evals-report-file are such tokens,
                # so the second run into a case directory silently lifts rootdir
                # to the repo root and every emitted nodeid changes shape.
                #
                # That is the whole root cause of the sealed-split corruption:
                # first run -> files absent -> rootdir = evals project ->
                # classname "tests.test_agentic"; second run -> files present ->
                # rootdir = repo root -> classname
                # "benchmarks.agentic.evals.tests.test_agentic", which the parser
                # could not map back to a configured case. Measured across runs/:
                # every scorecard split is the long shape, every train/holdout is
                # the short one — and mvp2-evolve's train has 10 long ones, from
                # a resumed stage re-running into existing directories.
                summary_path.unlink(missing_ok=True)
                junit_path.unlink(missing_ok=True)
                command = self._base_command(experiment)
                if summary_flag := experiment.runner_config.get("summary_flag", "--evals-report-file"):
                    command.extend([str(summary_flag), str(summary_path)])
                command.extend(["--junitxml", str(junit_path)])
                command.extend(str(arg) for arg in experiment.runner_config.get("pytest_args", ["-q"]))
                command.append(rendered)

                (case_dir / "command.json").write_text(
                    json.dumps(
                        {
                            "argv": command,
                            "shell": shlex.join(command),
                            "cwd": str(project_root),
                            "env": {
                                VARIANT_ENV: str(variant_path),
                                "PYTHONPATH": env["PYTHONPATH"],
                                "LANGSMITH_TEST_SUITE": env["LANGSMITH_TEST_SUITE"],
                            },
                        },
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                )

                completed = subprocess.run(
                    command,
                    cwd=project_root,
                    env=env,
                    capture_output=True,
                    check=False,
                    text=True,
                )
                (case_dir / "stdout.log").write_text(completed.stdout)
                (case_dir / "stderr.log").write_text(completed.stderr)
                split_stdout.append(f"## {rendered}\n{completed.stdout}")
                split_stderr.append(f"## {rendered}\n{completed.stderr}")
                returncodes.append(completed.returncode)

                case_outcome = parse_pytest_outcomes(
                    junit_path=junit_path,
                    cases=[case],
                    model=experiment.model,
                    artifacts_dir=case_dir,
                )[0]

                if summary_path.exists():
                    summary_payload: dict[str, Any] | None = json.loads(summary_path.read_text())
                else:
                    summary_payload = {
                        "passed": 1 if case_outcome.passed else 0,
                        "total": 1,
                        "correctness": 1.0 if case_outcome.passed else 0.0,
                    }
                    summary_path.write_text(json.dumps(summary_payload, indent=2) + "\n")

                if isinstance(summary_payload, dict):
                    fingerprints.update(
                        str(item) for item in summary_payload.get("system_fingerprints", []) or []
                    )

                trace_refs = extract_trace_refs(
                    payload=summary_payload,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                )
                write_trace_refs(case_dir, trace_refs)
                case_outcome = CaseOutcome(
                    case_id=case_outcome.case_id,
                    split=case_outcome.split,
                    stratum=case_outcome.stratum,
                    status=case_outcome.status,
                    score=case_outcome.score,
                    duration_s=case_outcome.duration_s,
                    failure_message=case_outcome.failure_message,
                    artifacts_dir=str(case_dir),
                    trace_ref=trace_refs[0] if trace_refs else None,
                )
                outcomes.append(case_outcome)

        (split_dir / "stdout.log").write_text("\n\n".join(split_stdout))
        (split_dir / "stderr.log").write_text("\n\n".join(split_stderr))
        outcomes = mark_apparatus_outcomes(outcomes)
        apparatus = sum(1 for outcome in outcomes if outcome.is_apparatus)
        passed = sum(1 for outcome in outcomes if outcome.passed)
        total = len(outcomes) - apparatus
        summary_payload = {
            "passed": passed,
            "failed": sum(1 for outcome in outcomes if outcome.status == "failed"),
            "skipped": sum(1 for outcome in outcomes if outcome.status == "skipped"),
            "apparatus": apparatus,
            "total": total,
            "correctness": 0.0 if total == 0 else passed / total,
            "system_fingerprints": sorted(fingerprints),
        }
        (split_dir / "summary.json").write_text(json.dumps(summary_payload, indent=2) + "\n")

        result = SplitResult(
            split=split,
            variant=variant.key,
            model=experiment.model,
            passed=passed,
            total=total,
            score=float(passed),
            returncode=max(returncodes) if returncodes else 0,
            run_dir=str(split_dir),
            outcomes=tuple(outcomes),
            apparatus=apparatus,
            fingerprints=tuple(sorted(fingerprints)),
        )
        result.save(result_path)
        return result

    def _build_env(self, *, experiment: Experiment, variant_path: Path, runtime_dir: Path) -> dict[str, str]:
        env = os.environ.copy()
        env[VARIANT_ENV] = str(variant_path)
        env["PYTHONPATH"] = prepend_pythonpath(
            [runtime_dir, self.repo_root, experiment.workspace_root],
            env.get("PYTHONPATH"),
        )
        env.setdefault("LANGSMITH_TEST_SUITE", f"better-harness-{experiment.name}")
        return env

    def _base_command(self, experiment: Experiment) -> list[str]:
        project_root = Path(str(experiment.runner_config["project_root"]))
        command = ["uv", "run", "--project", str(project_root)]
        if group := experiment.runner_config.get("uv_group", "test"):
            command.extend(["--group", str(group)])
        command.append("pytest")
        if model_flag := experiment.runner_config.get("model_flag"):
            command.extend([str(model_flag), experiment.model])
        command.extend(["-p", "better_harness_plugin"])
        return command


class HarborRunner:
    """Run Harbor tasks one case at a time."""

    def __init__(self, *, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parents[1]

    def collect_inventory(self, experiment: Experiment) -> list[str]:
        """Collect Harbor task names by scanning the tasks directory."""
        tasks_root = Path(str(experiment.runner_config["tasks_root"]))
        inventory = [
            str(path.parent.relative_to(tasks_root))
            for path in tasks_root.rglob("task.toml")
        ]
        return sorted(inventory)

    def run_split(
        self,
        *,
        experiment: Experiment,
        variant: Variant,
        split: str,
        layout: RunLayout,
        reuse_existing: bool = False,
    ) -> SplitResult:
        """Run one Harbor split."""
        split_dir = layout.split_dir(variant_key=variant.key, split=split)
        result_path = split_dir / "result.json"
        variant_path = layout.variant_path(variant.key)
        if reuse_existing:
            reused = reusable_result(
                result_path=result_path,
                variant=variant,
                variant_path=variant_path,
            )
            if reused is not None:
                return reused

        split_dir.mkdir(parents=True, exist_ok=True)
        variant.save(variant_path)
        cases = experiment.cases_for_split(split)
        outcomes: list[CaseOutcome] = []
        returncodes: list[int] = []

        for case in cases:
            rendered = case.render(model=experiment.model)
            case_slug = safe_slug(rendered)
            case_dir = split_dir / case_slug
            case_dir.mkdir(parents=True, exist_ok=True)
            jobs_dir = case_dir / "jobs"
            command = self._build_command(
                experiment=experiment,
                task_name=rendered,
                jobs_dir=jobs_dir,
                job_name=case_slug,
            )
            env = os.environ.copy()
            runtime_dir = ensure_sitecustomize(layout.runtime_dir)
            env[VARIANT_ENV] = str(variant_path)
            env["BETTER_HARNESS_WORKSPACE_ROOT"] = str(experiment.workspace_root)
            env["PYTHONPATH"] = prepend_pythonpath(
                [runtime_dir, self.repo_root, experiment.workspace_root],
                env.get("PYTHONPATH"),
            )
            (case_dir / "command.json").write_text(
                json.dumps(
                    {
                        "argv": command,
                        "shell": shlex.join(command),
                        "cwd": str(experiment.workspace_root),
                        "env": {
                            VARIANT_ENV: str(variant_path),
                            "BETTER_HARNESS_WORKSPACE_ROOT": str(experiment.workspace_root),
                            "PYTHONPATH": env["PYTHONPATH"],
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            with workspace_override_context(experiment.workspace_root, variant.file_overrides()):
                completed = subprocess.run(
                    command,
                    cwd=experiment.workspace_root,
                    env=env,
                    capture_output=True,
                    check=False,
                    text=True,
                )
            (case_dir / "stdout.log").write_text(completed.stdout)
            (case_dir / "stderr.log").write_text(completed.stderr)
            returncodes.append(completed.returncode)

            score, payload, failure_message = parse_harbor_case(
                jobs_dir=jobs_dir,
                pass_threshold=float(experiment.runner_config.get("pass_threshold", 1.0)),
            )
            trace_refs = extract_trace_refs(
                payload=payload,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
            write_trace_refs(case_dir, trace_refs)
            status = "passed" if score >= float(experiment.runner_config.get("pass_threshold", 1.0)) else "failed"
            outcomes.append(
                CaseOutcome(
                    case_id=rendered,
                    split=split,
                    stratum=case.stratum,
                    status=status,
                    score=score,
                    duration_s=0.0,
                    failure_message=failure_message,
                    artifacts_dir=str(case_dir),
                    trace_ref=trace_refs[0] if trace_refs else None,
                )
            )

        outcomes = list(mark_apparatus_outcomes(outcomes))
        apparatus = sum(1 for outcome in outcomes if outcome.is_apparatus)
        passed = sum(1 for outcome in outcomes if outcome.passed)
        result = SplitResult(
            split=split,
            variant=variant.key,
            model=experiment.model,
            passed=passed,
            total=len(outcomes) - apparatus,
            score=float(sum(outcome.score for outcome in outcomes)),
            returncode=max(returncodes, default=0),
            run_dir=str(split_dir),
            outcomes=tuple(outcomes),
            apparatus=apparatus,
        )
        result.save(result_path)
        summary_payload = {
            "passed": result.passed,
            "total": result.total,
            "correctness": result.correctness,
            "score": result.score,
        }
        (split_dir / "summary.json").write_text(json.dumps(summary_payload, indent=2) + "\n")
        return result

    def _build_command(
        self,
        *,
        experiment: Experiment,
        task_name: str,
        jobs_dir: Path,
        job_name: str,
    ) -> list[str]:
        config = experiment.runner_config
        command = [str(item) for item in config["command"]]
        command.extend(
            [
                "run",
                "-p",
                str(config["tasks_root"]),
                "--task-name",
                task_name,
                "-l",
                "1",
                "-n",
                str(config.get("concurrency", 1)),
            ]
        )
        if agent_import_path := config.get("agent_import_path"):
            command.extend(["--agent-import-path", str(agent_import_path)])
        command.extend(["-o", str(jobs_dir), "--job-name", job_name])
        command.extend(str(item) for item in config.get("extra_args", []))
        return command


def build_runner(experiment: Experiment):
    """Build the configured runner."""
    if experiment.runner == "pytest":
        return PytestRunner()
    if experiment.runner == "harbor":
        return HarborRunner()
    if experiment.runner == "coding":
        return CodingProjectRunner()
    msg = f"unknown runner {experiment.runner!r}"
    raise ValueError(msg)


def mark_apparatus_outcomes(outcomes: list[CaseOutcome]) -> list[CaseOutcome]:
    """Re-label outcomes whose failure was the measurement, not the agent.

    Applied once, at the boundary where raw runner output becomes a
    ``SplitResult``, so every consumer downstream — gate, cost veto, signature
    clustering, ledger, analysis scripts — sees the same partition.
    """
    marked: list[CaseOutcome] = []
    for outcome in outcomes:
        if outcome.passed or outcome.is_apparatus:
            marked.append(outcome)
            continue
        kind = apparatus_kind(outcome.failure_message)
        if kind is None:
            marked.append(outcome)
            continue
        marked.append(
            replace(
                outcome,
                status=STATUS_APPARATUS,
                score=0.0,
                failure_message=f"[apparatus:{kind}] {outcome.failure_message or ''}".strip(),
            )
        )
    return marked


def parse_pytest_outcomes(
    *,
    junit_path: Path,
    cases: list[EvalCase],
    model: str,
    artifacts_dir: Path,
) -> list[CaseOutcome]:
    """Parse JUnit results for configured cases."""
    root = ET.fromstring(junit_path.read_text())
    configured = {case.render(model=model): case for case in cases}
    testcases = list(root.iter("testcase"))
    outcomes: dict[str, CaseOutcome] = {}
    for testcase in testcases:
        case_id = resolve_case_id(
            file_attr=testcase.attrib.get("file", ""),
            classname_attr=testcase.attrib.get("classname", ""),
            name_attr=testcase.attrib.get("name", ""),
            configured=configured,
            sole_candidate=len(configured) == 1 and len(testcases) == 1,
        )
        case = configured.get(case_id) if case_id else None
        if case is None:
            continue
        status = "passed"
        failure_message = None
        failure = testcase.find("failure")
        if failure is None:
            failure = testcase.find("error")
        if failure is not None:
            status = "failed"
            failure_message = failure.text or failure.attrib.get("message")
        elif testcase.find("skipped") is not None:
            status = "skipped"
        outcomes[case_id] = CaseOutcome(
            case_id=case_id,
            split=case.split,
            stratum=case.stratum,
            status=status,
            score=1.0 if status == "passed" else 0.0,
            duration_s=float(testcase.attrib.get("time", "0") or "0"),
            failure_message=failure_message,
            artifacts_dir=str(artifacts_dir),
        )
    unresolved = [case for case in cases if case.render(model=model) not in outcomes]
    if unresolved and testcases:
        # pytest recorded results and we could not map them. That is a defect in
        # this parser, not an outcome of the experiment, and recording a zero
        # would make the two indistinguishable — which is precisely how every
        # sealed-split evaluation in this repo came to read 0/20 against a true
        # 17-18/20, with nothing anywhere reporting a problem.
        raise UnresolvedCaseError(
            junit_path=junit_path,
            case_ids=[case.render(model=model) for case in unresolved],
            observed=[
                f"file={tc.attrib.get('file', '')!r} "
                f"classname={tc.attrib.get('classname', '')!r} "
                f"name={tc.attrib.get('name', '')!r}"
                for tc in testcases
            ],
        )
    # No testcases at all: the process died before pytest wrote any result. That
    # is an apparatus failure — nothing was measured — and it is excluded from
    # the numerator and the denominator rather than aborting a 180-rollout stage.
    return [
        outcomes.get(
            case.render(model=model),
            CaseOutcome(
                case_id=case.render(model=model),
                split=case.split,
                stratum=case.stratum,
                status=STATUS_APPARATUS,
                score=0.0,
                duration_s=0.0,
                failure_message="[apparatus:junit_unreadable] junit.xml recorded no testcase",
                artifacts_dir=str(artifacts_dir),
            ),
        )
        for case in cases
    ]


def rebuild_case_id(*, file_attr: str, classname_attr: str, name_attr: str) -> str:
    """Best-effort reconstruction of a pytest nodeid from JUnit fields."""
    if file_attr:
        return f"{file_attr}::{name_attr}"
    if classname_attr.startswith("tests."):
        return f"{classname_attr.replace('.', '/')}.py::{name_attr}"
    return name_attr


class UnresolvedCaseError(RuntimeError):
    """A junit.xml recorded testcases but none could be mapped to a configured case.

    Raised instead of recording a zero. A parse miss and a task failure are
    different events, and the moment they become the same number the whole
    experiment is measuring its own parser. The message carries every observed
    ``file``/``classname``/``name`` triple, because that is exactly what is
    needed to add the missing shape and nothing else is.
    """

    def __init__(self, *, junit_path: Path, case_ids: Sequence[str], observed: Sequence[str]) -> None:
        seen = "; ".join(observed) if observed else "<no testcase elements>"
        super().__init__(
            f"{junit_path}: could not resolve {', '.join(case_ids)} from junit.xml. "
            f"Recorded testcases: {seen}"
        )


def _nodeid_candidates(*, file_attr: str, classname_attr: str, name_attr: str) -> list[str]:
    """Return every plausible pytest nodeid for one JUnit testcase.

    ``classname`` is the module path with ``.`` separators and, when a test lives
    in a class, the class name appended. Where the module path ends and the class
    names begin is not recoverable from the string, so every split point is
    offered as a candidate and the caller picks by matching against ids it knows.
    """
    candidates: list[str] = []
    if file_attr:
        candidates.append(f"{file_attr}::{name_attr}")
    if classname_attr:
        parts = classname_attr.split(".")
        for cut in range(len(parts), 0, -1):
            module = "/".join(parts[:cut]) + ".py"
            suffix = "::".join(parts[cut:])
            candidates.append(f"{module}::{suffix}::{name_attr}" if suffix else f"{module}::{name_attr}")
    return candidates


def _same_nodeid(candidate: str, case_id: str) -> bool:
    """Return whether two nodeids denote the same case under a different rootdir.

    Equality, or one being a path-suffix of the other: a rootdir lift only ever
    prepends directory components, so
    ``benchmarks/agentic/evals/tests/test_agentic.py::test_task[x]`` and
    ``tests/test_agentic.py::test_task[x]`` are the same case.
    """
    return candidate == case_id or candidate.endswith(f"/{case_id}") or case_id.endswith(f"/{candidate}")


def resolve_case_id(
    *,
    file_attr: str,
    classname_attr: str,
    name_attr: str,
    configured: dict[str, EvalCase],
    sole_candidate: bool,
) -> str | None:
    """Map one JUnit ``testcase`` back to a configured case id, or None.

    Reconstructing a nodeid from JUnit attributes is guesswork, and the two
    shapes :func:`rebuild_case_id` handles are not the only ones pytest emits.
    This suite's XML has no ``file`` attribute and a rootdir-relative dotted
    classname (``benchmarks.agentic.evals.tests.test_agentic``), so the guess
    matched no configured case, the real outcome was dropped, and the case was
    recorded as ``missing`` with score 0 — in every scorecard evaluation across
    five runs, against true scores of 17-18/20.

    So resolution now falls back from guessing to *matching*: the configured ids
    are known, and a JUnit ``name`` that uniquely identifies one of them is
    enough. The last resort uses the strongest fact available in the pytest
    runner — it invokes pytest once per case, so a single testcase in a file
    written for a single configured case can only be that case.
    """
    candidates = _nodeid_candidates(
        file_attr=file_attr,
        classname_attr=classname_attr,
        name_attr=name_attr,
    )
    # Longest match wins: the most specific candidate that still denotes a
    # configured case is the least likely to be a coincidence. A tie at the same
    # specificity is a genuine ambiguity and must not be broken arbitrarily —
    # guessing there would attach one case's result to another, which is worse
    # than reporting nothing because it looks like a valid outcome.
    best_len = -1
    best_ids: set[str] = set()
    for candidate in candidates:
        for case_id in configured:
            if not _same_nodeid(candidate, case_id):
                continue
            if len(candidate) > best_len:
                best_len, best_ids = len(candidate), {case_id}
            elif len(candidate) == best_len:
                best_ids.add(case_id)
    if len(best_ids) == 1:
        return next(iter(best_ids))
    if best_ids:
        return None
    if name_attr:
        suffix = f"::{name_attr}"
        matches = [case_id for case_id in configured if case_id.endswith(suffix)]
        if len(matches) == 1:
            return matches[0]
    if sole_candidate:
        # Last resort, and it rests on a property of the caller rather than of
        # the data: the pytest runner invokes pytest once per case. Kept because
        # it is true here, but reached only when the id matching above found
        # nothing, which after the candidate expansion should be never.
        return next(iter(configured))
    return None


def parse_harbor_case(*, jobs_dir: Path, pass_threshold: float) -> tuple[float, dict[str, object] | None, str | None]:
    """Parse one Harbor task result."""
    payload = None
    score = 0.0
    failure_message: str | None = None
    json_paths = sorted(jobs_dir.rglob("result.json"))
    if json_paths:
        payload = json.loads(json_paths[0].read_text())
        score = float(payload.get("score", payload.get("reward", 0.0)))
        failure_message = None if score >= pass_threshold else str(payload.get("message", "score below threshold"))
        return score, payload, failure_message

    reward_paths = sorted(jobs_dir.rglob("reward.txt"))
    if reward_paths:
        raw_score = reward_paths[0].read_text().strip()
        score = float(raw_score or "0")
        payload = {"score": score}
        failure_message = None if score >= pass_threshold else "score below threshold"
        return score, payload, failure_message

    return 0.0, None, "missing Harbor result files"


def safe_slug(value: str) -> str:
    """Return a filesystem-safe slug."""
    cleaned = [
        character if character.isalnum() else "-"
        for character in value
    ]
    slug = "".join(cleaned).strip("-")
    return slug or "case"
