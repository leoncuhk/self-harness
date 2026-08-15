"""Coding-project inner loop: agent edits a product, frozen CI judges the diff."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from self_harness.apparatus import STATUS_APPARATUS
from self_harness.core import (
    CaseOutcome,
    Experiment,
    RunLayout,
    SplitResult,
    Variant,
    reusable_result,
)
from self_harness.patching import materialize_workspace


@dataclass(frozen=True)
class CommandResult:
    """Auditable result of one external command."""

    argv: tuple[str, ...]
    returncode: int
    duration_s: float
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize without losing the exact command or output."""
        return {
            "argv": list(self.argv),
            "returncode": self.returncode,
            "duration_s": self.duration_s,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def _render_tokens(tokens: Sequence[str], values: dict[str, str]) -> list[str]:
    rendered: list[str] = []
    for token in tokens:
        value = str(token)
        for key, replacement in values.items():
            value = value.replace("{" + key + "}", replacement)
        rendered.append(value)
    return rendered


def _run_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout_s: float,
    env: dict[str, str] | None = None,
) -> CommandResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            env=env,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_s,
        )
        return CommandResult(
            argv=tuple(str(item) for item in argv),
            returncode=completed.returncode,
            duration_s=time.monotonic() - started,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return CommandResult(
            argv=tuple(str(item) for item in argv),
            returncode=124,
            duration_s=time.monotonic() - started,
            stdout=stdout,
            stderr=f"{stderr}\ncommand timed out after {timeout_s}s".strip(),
        )


def _copy_product(source: Path, destination: Path) -> None:
    """Create a clean product seed without VCS and runtime caches."""
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
            "*.pyc",
        ),
    )


def _file_manifest(root: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = str(path.relative_to(root))
        manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def _changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _write_trace(path: Path, events: Sequence[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events))


def _safe_slug(value: str) -> str:
    slug = "".join(character if character.isalnum() else "-" for character in value).strip("-")
    return slug or "case"


class CodingProjectRunner:
    """Run a coding agent against disposable product copies and frozen CI."""

    def collect_inventory(self, experiment: Experiment) -> list[str]:
        """List task paths relative to the configured task root."""
        task_root = Path(str(experiment.runner_config["task_root"]))
        return sorted(
            str(path.relative_to(task_root)) for path in task_root.rglob("*") if path.is_file()
        )

    def run_split(
        self,
        *,
        experiment: Experiment,
        variant: Variant,
        split: str,
        layout: RunLayout,
        reuse_existing: bool = False,
    ):
        """Run every coding task in one split from the same product seed."""
        split_dir = layout.split_dir(variant_key=variant.key, split=split)
        result_path = split_dir / "result.json"
        variant_path = layout.variant_path(variant.key)
        if reuse_existing:
            reused = reusable_result(
                result_path=result_path,
                variant=variant,
                variant_path=variant_path,
                evaluation_fingerprint=experiment.evaluation_fingerprint,
            )
            if reused is not None:
                return reused

        if split_dir.exists():
            shutil.rmtree(split_dir)
        split_dir.mkdir(parents=True, exist_ok=True)
        variant.save(variant_path)
        task_root = Path(str(experiment.runner_config["task_root"]))
        product_root = Path(str(experiment.runner_config["product_root"]))
        keep_workspaces = bool(experiment.runner_config.get("keep_workspaces", False))
        timeout_s = float(experiment.runner_config.get("timeout_s", 900))
        ci_timeout_s = float(experiment.runner_config.get("ci_timeout_s", 600))
        agent_template = [str(item) for item in experiment.runner_config["agent_command"]]
        ci_templates = [
            [str(item) for item in command] for command in experiment.runner_config["ci_commands"]
        ]

        outcomes: list[CaseOutcome] = []
        returncodes: list[int] = []
        for case in experiment.cases_for_split(split):
            rendered = case.render(model=experiment.model)
            task_path = task_root / rendered
            case_dir = split_dir / "cases" / _safe_slug(rendered)
            case_dir.mkdir(parents=True, exist_ok=True)
            harness_dir = materialize_workspace(
                experiment.workspace_root,
                artifacts_dir=case_dir / "harnesses",
                overrides=variant.file_overrides(),
            )
            product_dir = case_dir / "product"
            _copy_product(product_root, product_dir)
            before = _file_manifest(product_dir)
            trace_path = case_dir / "trace.jsonl"
            values = {
                "workspace": str(product_dir),
                "product": str(product_dir),
                "task": str(task_path),
                "task_file": str(task_path),
                "harness": str(harness_dir),
                "trace": str(trace_path),
                "model": experiment.model,
            }
            agent_argv = _render_tokens(agent_template, values)
            env = os.environ.copy()
            env.update(
                {
                    "SELF_HARNESS_PRODUCT": str(product_dir),
                    "SELF_HARNESS_TASK": str(task_path),
                    "SELF_HARNESS_ROOT": str(harness_dir),
                    "SELF_HARNESS_TRACE": str(trace_path),
                    "SELF_HARNESS_MODEL": experiment.model,
                }
            )
            events: list[dict[str, Any]] = [
                {"event": "inner_start", "task": rendered, "variant": variant.key}
            ]
            agent_result = _run_command(
                agent_argv,
                cwd=product_dir,
                timeout_s=timeout_s,
                env=env,
            )
            (case_dir / "agent.json").write_text(
                json.dumps(agent_result.to_dict(), indent=2, sort_keys=True) + "\n"
            )
            events.append(
                {
                    "event": "agent_end",
                    "returncode": agent_result.returncode,
                    "duration_s": agent_result.duration_s,
                }
            )

            ci_results: list[CommandResult] = []
            if agent_result.returncode == 0:
                for index, template in enumerate(ci_templates):
                    ci_argv = _render_tokens(template, values)
                    ci_result = _run_command(
                        ci_argv, cwd=product_dir, timeout_s=ci_timeout_s, env=env
                    )
                    ci_results.append(ci_result)
                    events.append(
                        {
                            "event": "ci_end",
                            "index": index,
                            "argv": ci_argv,
                            "returncode": ci_result.returncode,
                            "duration_s": ci_result.duration_s,
                        }
                    )
            (case_dir / "ci.json").write_text(
                json.dumps([item.to_dict() for item in ci_results], indent=2, sort_keys=True) + "\n"
            )
            after = _file_manifest(product_dir)
            changed = _changed_files(before, after)
            (case_dir / "product_diff.json").write_text(
                json.dumps({"changed_files": changed}, indent=2, sort_keys=True) + "\n"
            )
            events.append({"event": "product_diff", "changed_files": changed})
            _write_trace(trace_path, events)

            ci_passed = sum(item.returncode == 0 for item in ci_results)
            ci_total = len(ci_templates)
            score = 0.0 if ci_total == 0 else ci_passed / ci_total
            passed = agent_result.returncode == 0 and ci_total > 0 and ci_passed == ci_total
            if agent_result.returncode == 124:
                status = STATUS_APPARATUS
                failure = "[apparatus:agent_timeout] coding agent timed out"
            elif agent_result.returncode != 0:
                status = "failed"
                failure = agent_result.stderr or f"coding agent exited {agent_result.returncode}"
            elif not passed:
                status = "failed"
                failed = next((item for item in ci_results if item.returncode != 0), None)
                failure = (
                    "CI failed"
                    if failed is None
                    else (failed.stderr or failed.stdout or "CI failed")
                )
            else:
                status = "passed"
                failure = None
            duration = agent_result.duration_s + sum(item.duration_s for item in ci_results)
            outcomes.append(
                CaseOutcome(
                    case_id=rendered,
                    split=split,
                    stratum=case.stratum,
                    status=status,
                    score=score,
                    duration_s=duration,
                    failure_message=failure,
                    artifacts_dir=str(case_dir),
                    trace_ref=str(trace_path),
                    metrics={
                        "ci_pass_rate": score,
                        "changed_files": float(len(changed)),
                    },
                )
            )
            returncodes.extend([agent_result.returncode, *(item.returncode for item in ci_results)])
            if not keep_workspaces:
                shutil.rmtree(product_dir)

        apparatus = sum(outcome.is_apparatus for outcome in outcomes)
        measured = [outcome for outcome in outcomes if not outcome.is_apparatus]
        result = SplitResult(
            split=split,
            variant=variant.key,
            model=experiment.model,
            passed=sum(outcome.passed for outcome in measured),
            total=len(measured),
            score=sum(outcome.score for outcome in measured),
            returncode=max(returncodes, default=0),
            run_dir=str(split_dir),
            outcomes=tuple(outcomes),
            apparatus=apparatus,
            metrics={
                "ci_pass_rate": 0.0
                if not measured
                else sum(outcome.metrics["ci_pass_rate"] for outcome in measured) / len(measured),
            },
            evaluation_fingerprint=experiment.evaluation_fingerprint,
        )
        result.save(result_path)
        (split_dir / "summary.json").write_text(
            json.dumps(
                {
                    "passed": result.passed,
                    "total": result.total,
                    "score": result.score,
                    "correctness": result.correctness,
                    "apparatus": apparatus,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return result
