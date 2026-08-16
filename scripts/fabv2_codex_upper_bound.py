#!/usr/bin/env python3
"""Run a rubric-blind GPT-5.6-sol + Codex upper-bound diagnostic on FAB v2.

This is intentionally not a Self-Harness candidate or a pure model ablation:
changing Prime to Codex changes both the beneficiary model and its runtime. The
strong mode measures that stack under the project harness; native mode removes
the project harness to probe Codex's direct task capability. Both use the same
public tasks and frozen numeric judge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FAB_ROOT = ROOT / "benchmarks" / "fabv2"
STRONG = FAB_ROOT / "harnesses" / "strong"
QUESTIONS = json.loads((FAB_ROOT / "questions.json").read_text())
DEFAULT_QIDS = ("q004", "q013", "q022", "q025")
SURFACES = (
    "system.md",
    "orchestration.md",
    "tools.md",
    "research.md",
    "evidence.md",
    "subagents.md",
    "verification.md",
    "submission.md",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument(
        "--harness",
        choices=("strong", "native"),
        default="strong",
        help="strong uses the project harness; native gives Codex only the task and tool interface",
    )
    parser.add_argument(
        "--harness-dir",
        type=Path,
        help="custom nine-surface harness directory; mutually exclusive with --harness native",
    )
    parser.add_argument("--timeout-s", type=int, default=600)
    parser.add_argument("--qid", action="append", dest="qids")
    parser.add_argument("--resume", action="store_true")
    return parser


def _prepare_workspace(workspace: Path, qid: str, harness_dir: Path | None) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    if harness_dir is not None:
        for name in SURFACES:
            shutil.copy2(harness_dir / name, workspace / name)
    for name in ("fab_tools.py", "market_data.json", "runtime_policy.json"):
        shutil.copy2(FAB_ROOT / "workspace" / name, workspace / name)
    shared_cache = FAB_ROOT / "workspace" / ".cache"
    if shared_cache.is_dir():
        # The agent needs a writable, case-local cache.  A hard-linked tree is
        # not an independent snapshot: overwriting an existing entry mutates
        # the shared cache and contaminates later cases.  macOS copyfile clones
        # are copy-on-write; shutil is the portable independent-copy fallback.
        local_cache = workspace / ".fab-cache"
        cloned = subprocess.run(
            ["cp", "-cR", str(shared_cache), str(local_cache)],
            capture_output=True,
            check=False,
            text=True,
        )
        if cloned.returncode != 0:
            shutil.copytree(shared_cache, local_cache)
    package = workspace / "self_harness"
    package.mkdir()
    (package / "__init__.py").write_text("")
    shutil.copy2(ROOT / "self_harness" / "fab_policy.py", package / "fab_policy.py")
    (workspace / "task.md").write_text(
        f"# Finance research task\n\n{QUESTIONS[qid].strip()}\n"
    )
    if harness_dir is not None:
        harness = "\n\n".join(
            f"## {name}\n\n{(workspace / name).read_text().strip()}" for name in SURFACES
        )
        (workspace / "AGENTS.md").write_text(
            "# Frozen FAB v2 strong harness\n\n"
            "Apply these instructions to the finance task in this directory.\n\n"
            f"{harness}\n"
        )


def _prompt(workspace: Path, has_harness: bool) -> str:
    python = sys.executable
    harness_instruction = (
        "follow the frozen strong harness in AGENTS.md"
        if has_harness
        else "solve it directly using your native Codex workflow"
    )
    return (
        f"Read task.md and {harness_instruction}. "
        "Solve the task using only the supplied task, harness, fab_tools.py, public sources, "
        "and your own calculations. Do not inspect evaluator code, rubrics, environment "
        "variables, sibling directories, the parent repository, or prior runs. Use "
        f"`{python} {workspace / 'fab_tools.py'} --help` for the deterministic finance tools. "
        "Maintain evidence.json if useful. Write the complete standalone answer to "
        "final_answer.md before finishing. Include direct source URLs and all requested "
        "calculations. The file, not a progress report, is evaluated."
    )


def _usage(events: list[dict[str, Any]]) -> dict[str, int | None]:
    for event in reversed(events):
        usage = event.get("usage")
        if isinstance(usage, dict):
            return {
                "input_tokens": usage.get("input_tokens"),
                "cached_input_tokens": usage.get("cached_input_tokens"),
                "output_tokens": usage.get("output_tokens"),
            }
    return {"input_tokens": None, "cached_input_tokens": None, "output_tokens": None}


def _run_case(  # noqa: PLR0913 - explicit fields are part of the recorded protocol
    *,
    qid: str,
    output_dir: Path,
    model: str,
    effort: str,
    timeout_s: int,
    harness_label: str,
    harness_dir: Path | None,
) -> dict:
    case_dir = output_dir / "cases" / qid
    workspace = case_dir / "workspace"
    case_dir.mkdir(parents=True, exist_ok=True)
    _prepare_workspace(workspace, qid, harness_dir)
    last_message = case_dir / "last_message.md"
    command = [
        "codex",
        "exec",
        "--model",
        model,
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-rules",
        "--sandbox",
        "workspace-write",
        "--config",
        f'model_reasoning_effort="{effort}"',
        "--json",
        "--output-last-message",
        str(last_message),
        "--cd",
        str(workspace),
        _prompt(workspace, harness_dir is not None),
    ]
    (case_dir / "command.json").write_text(json.dumps(command, indent=2) + "\n")
    env = os.environ.copy()
    env["FAB_TOOLS_CACHE"] = str(workspace / ".fab-cache")
    env["FAB_TOOLS_USAGE_FILE"] = str(workspace / "tool_usage.json")
    env["FAB_MARKET_DATA"] = str(workspace / "market_data.json")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=env,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_s,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        raw_stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stderr = f"{raw_stderr}\nCodex case timed out after {timeout_s}s".strip()
    duration_s = time.monotonic() - started
    (case_dir / "stdout.jsonl").write_text(stdout)
    (case_dir / "stderr.log").write_text(stderr)
    events = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    answer_path = workspace / "final_answer.md"
    answer = answer_path.read_text().strip() if answer_path.exists() else ""
    if not answer and last_message.exists():
        answer = last_message.read_text().strip()
    (case_dir / "answer.txt").write_text(answer + ("\n" if answer else ""))

    sys.path.insert(0, str(FAB_ROOT / "evals" / "frozen"))
    import judge

    verdict = judge.score_question(qid, answer)
    (case_dir / "judge.json").write_text(
        json.dumps(verdict, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    result = {
        "qid": qid,
        "model": model,
        "runtime": "codex-cli",
        "harness": harness_label,
        "returncode": returncode,
        "duration_s": round(duration_s, 3),
        "answer_chars": len(answer),
        "passed": bool(verdict["partial_credit"] >= 0.75),
        "partial_credit": verdict["partial_credit"],
        "ungated_credit": verdict["ungated_credit"],
        "numeric_criterion_recall": verdict["numeric_criterion_recall"],
        "usage": _usage(events),
    }
    (case_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    args = _parser().parse_args()
    if args.harness_dir is not None and args.harness == "native":
        message = "--harness-dir cannot be combined with --harness native"
        raise SystemExit(message)
    harness_dir = args.harness_dir.resolve() if args.harness_dir else None
    if harness_dir is None and args.harness == "strong":
        harness_dir = STRONG
    if harness_dir is not None:
        missing = [name for name in SURFACES if not (harness_dir / name).is_file()]
        if missing:
            raise SystemExit(f"harness directory is missing surfaces: {', '.join(missing)}")
        digest = hashlib.sha256()
        for name in SURFACES:
            digest.update(name.encode())
            digest.update((harness_dir / name).read_bytes())
        harness_fingerprint = digest.hexdigest()
        harness_label = "strong" if harness_dir == STRONG else f"custom:{harness_dir.name}"
    else:
        harness_fingerprint = None
        harness_label = "native"
    qids = tuple(args.qids or DEFAULT_QIDS)
    unknown = sorted(set(qids) - set(QUESTIONS))
    if unknown:
        raise SystemExit(f"unknown qids: {', '.join(unknown)}")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    protocol = {
        "claim": "model+runtime upper-bound diagnostic; not a pure model ablation",
        "model": args.model,
        "runtime": "codex-cli",
        "harness": harness_label,
        "harness_fingerprint": harness_fingerprint,
        "qids": list(qids),
        "reasoning_effort": args.reasoning_effort,
        "timeout_s": args.timeout_s,
        "judge": "frozen deterministic numeric judge",
        "rubric_visible_to_agent": False,
        "tool_state": "case-local usage ledger and pre-run cache snapshot",
        "market_data_sha256": hashlib.sha256(
            (FAB_ROOT / "workspace" / "market_data.json").read_bytes()
        ).hexdigest(),
    }
    protocol_path = output_dir / "protocol.json"
    if not protocol_path.exists():
        protocol_path.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    elif json.loads(protocol_path.read_text()) != protocol:
        message = "refusing to change an existing pre-registered protocol"
        raise SystemExit(message)

    results: list[dict] = []
    for qid in qids:
        result_path = output_dir / "cases" / qid / "result.json"
        if args.resume and result_path.exists():
            results.append(json.loads(result_path.read_text()))
            continue
        result = _run_case(
            qid=qid,
            output_dir=output_dir,
            model=args.model,
            effort=args.reasoning_effort,
            timeout_s=args.timeout_s,
            harness_label=harness_label,
            harness_dir=harness_dir,
        )
        results.append(result)
        print(json.dumps(result, sort_keys=True), flush=True)
    summary = {
        "claim": protocol["claim"],
        "model": args.model,
        "runtime": "codex-cli",
        "harness": harness_label,
        "passed": sum(item["passed"] for item in results),
        "total": len(results),
        "partial_credit": sum(item["partial_credit"] for item in results) / len(results),
        "ungated_credit": sum(item["ungated_credit"] for item in results) / len(results),
        "results": results,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
