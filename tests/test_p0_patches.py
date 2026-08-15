"""Tests for the P0 patches: repeated evaluation and the conservative gate."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from better_harness.contracts import GoalContract
from better_harness.core import (
    CaseOutcome,
    Experiment,
    RunLayout,
    SplitResult,
    Surface,
    Variant,
    load_experiment,
)
from better_harness.gate import decide
from better_harness.repeats import aggregate_split_results, run_split_repeated


def make_outcome(case_id: str, *, passed: bool, duration_s: float = 1.0) -> CaseOutcome:
    """Build one case outcome."""
    return CaseOutcome(
        case_id=case_id,
        split="train",
        stratum="s",
        status="passed" if passed else "failed",
        score=1.0 if passed else 0.0,
        duration_s=duration_s,
        failure_message=None if passed else f"{case_id} boom",
        artifacts_dir=f"artifacts/{case_id}/{'ok' if passed else 'fail'}",
        trace_ref=None,
    )


def make_split(*, variant: str, results: dict[str, bool]) -> SplitResult:
    """Build one split result from a case_id -> passed mapping."""
    outcomes = tuple(make_outcome(case_id, passed=passed) for case_id, passed in results.items())
    passed = sum(1 for outcome in outcomes if outcome.passed)
    return SplitResult(
        split="train",
        variant=variant,
        model="m",
        passed=passed,
        total=len(outcomes),
        score=float(passed),
        returncode=0,
        run_dir="artifacts/run",
        outcomes=outcomes,
    )


# --------------------------------------------------------------------------
# P0-1 aggregation
# --------------------------------------------------------------------------


def test_aggregate_counts_attempts_not_cases(tmp_path: Path):
    """passed/total count attempts across repeats, so correctness is pass@1."""
    runs = [
        make_split(variant="v", results={"a": True, "b": True}),
        make_split(variant="v", results={"a": True, "b": False}),
        make_split(variant="v", results={"a": True, "b": False}),
    ]
    aggregated = aggregate_split_results(runs, run_dir=tmp_path)
    assert aggregated.total == 6  # 2 cases x 3 repeats
    assert aggregated.passed == 4  # a:3 + b:1
    assert aggregated.correctness == pytest.approx(4 / 6)


def test_aggregate_marks_flaky_and_keeps_stable_pass_semantics(tmp_path: Path):
    """A case passing only some repeats is flaky and never counts as a stable pass."""
    runs = [
        make_split(variant="v", results={"a": True, "b": True, "c": False}),
        make_split(variant="v", results={"a": True, "b": False, "c": False}),
    ]
    aggregated = aggregate_split_results(runs, run_dir=tmp_path)
    statuses = {outcome.case_id: outcome.status for outcome in aggregated.outcomes}
    assert statuses == {"a": "passed", "b": "flaky", "c": "failed"}
    assert aggregated.passing_case_ids() == {"a"}

    fractions = {outcome.case_id: outcome.score for outcome in aggregated.outcomes}
    assert fractions == {"a": 1.0, "b": 0.5, "c": 0.0}


def test_aggregate_points_evidence_at_a_failing_repeat(tmp_path: Path):
    """The outer agent must be shown a genuinely failing repeat, not a passing one."""
    runs = [
        make_split(variant="v", results={"b": True}),
        make_split(variant="v", results={"b": False}),
    ]
    aggregated = aggregate_split_results(runs, run_dir=tmp_path)
    outcome = aggregated.outcomes[0]
    assert outcome.artifacts_dir == "artifacts/b/fail"
    assert outcome.failure_message == "b boom"


def test_aggregate_single_run_is_passthrough(tmp_path: Path):
    """repeats=1 must behave exactly like upstream."""
    single = make_split(variant="v", results={"a": True, "b": False})
    aggregated = aggregate_split_results([single], run_dir=tmp_path)
    assert (aggregated.passed, aggregated.total) == (1, 2)
    assert aggregated.outcomes == single.outcomes


def test_aggregate_rejects_empty(tmp_path: Path):
    with pytest.raises(ValueError, match="at least one result"):
        aggregate_split_results([], run_dir=tmp_path)


# --------------------------------------------------------------------------
# P0-1 wiring: repeats isolate their artifacts and are actually re-run
# --------------------------------------------------------------------------


class RecordingRunner:
    """Runner double that returns a scripted outcome per invocation."""

    def __init__(self, scripted: list[dict[str, bool]]) -> None:
        self.scripted = scripted
        self.calls: list[Path] = []

    def run_split(self, *, variant, split, layout, **_kwargs):
        split_dir = layout.split_dir(variant_key=variant.key, split=split)
        split_dir.mkdir(parents=True, exist_ok=True)
        self.calls.append(split_dir)
        return make_split(variant=variant.key, results=self.scripted[len(self.calls) - 1])


def make_experiment(tmp_path: Path, *, repeats: int) -> Experiment:
    """Build a minimal in-memory experiment."""
    return Experiment(
        path=tmp_path / "config.toml",
        name="t",
        runner="pytest",
        workspace_root=tmp_path,
        model="m",
        max_iterations=1,
        better_agent_model="m",
        better_agent_max_turns=1,
        better_agent_deepagents_root=None,
        better_agent_system_prompt=None,
        runner_config={},
        surfaces={"p": Surface(name="p", kind="module_attr", target="a:B", filename="p.txt", base_value="x")},
        cases=(),
        repeats=repeats,
    )


def make_variant() -> Variant:
    """Build one baseline variant."""
    surface = Surface(name="p", kind="module_attr", target="a:B", filename="p.txt", base_value="x")
    return Variant(
        label="baseline",
        model="m",
        changed_surfaces=(),
        surfaces={"p": surface},
        values={"p": "x"},
    )


def test_run_split_repeated_isolates_each_repeat(tmp_path: Path):
    """Each repeat writes into its own repNN directory and the runner really re-runs."""
    experiment = make_experiment(tmp_path, repeats=3)
    layout = RunLayout(tmp_path / "run")
    variant = make_variant()
    runner = RecordingRunner([{"a": True}, {"a": False}, {"a": True}])

    result = run_split_repeated(
        runner,
        experiment=experiment,
        variant=variant,
        split="train",
        layout=layout,
    )

    assert len(runner.calls) == 3
    assert [path.name for path in runner.calls] == ["rep00", "rep01", "rep02"]
    assert len({str(path) for path in runner.calls}) == 3
    assert (result.passed, result.total) == (2, 3)

    base = layout.split_dir(variant_key=variant.key, split="train")
    assert (base / "result.json").exists()
    detail = (base / "repeats.json").read_text()
    assert '"repeats": 3' in detail
    assert '"pass_fraction": 0.6666666666666666' in detail


def test_run_split_repeated_with_one_repeat_uses_base_dir(tmp_path: Path):
    """repeats=1 keeps the upstream directory layout untouched."""
    experiment = make_experiment(tmp_path, repeats=1)
    layout = RunLayout(tmp_path / "run")
    variant = make_variant()
    runner = RecordingRunner([{"a": True}])

    run_split_repeated(runner, experiment=experiment, variant=variant, split="train", layout=layout)

    assert runner.calls == [layout.split_dir(variant_key=variant.key, split="train")]


# --------------------------------------------------------------------------
# P0-2 gate
# --------------------------------------------------------------------------


def gate_case(*, gate: str, train_before, train_after, ho_before, ho_after):
    """Run one gate decision from four case_id -> passed mappings."""
    return decide(
        gate=gate,
        current_train=make_split(variant="cur", results=train_before),
        current_holdout=make_split(variant="cur", results=ho_before),
        candidate_train=make_split(variant="cand", results=train_after),
        candidate_holdout=make_split(variant="cand", results=ho_after),
    )


def test_conservative_gate_rejects_robbing_holdout_to_pay_train():
    """The exact overfitting shape upstream's combined gate promotes."""
    kwargs = {
        "train_before": {"t1": False, "t2": False, "t3": False},
        "train_after": {"t1": True, "t2": True, "t3": True},
        "ho_before": {"h1": True, "h2": True},
        "ho_after": {"h1": False, "h2": False},
    }
    conservative = gate_case(gate="conservative", **kwargs)
    combined = gate_case(gate="combined", **kwargs)

    assert conservative.delta_in == 3
    assert conservative.delta_ho == -2
    assert conservative.accepted is False
    assert "holdout regressed" in conservative.reason
    # upstream would have promoted this candidate
    assert combined.accepted is True


def test_conservative_gate_accepts_train_gain_with_flat_holdout():
    decision = gate_case(
        gate="conservative",
        train_before={"t1": False},
        train_after={"t1": True},
        ho_before={"h1": True},
        ho_after={"h1": True},
    )
    assert decision.accepted is True
    assert (decision.delta_in, decision.delta_ho) == (1, 0)


def test_conservative_gate_accepts_holdout_gain_with_flat_train():
    decision = gate_case(
        gate="conservative",
        train_before={"t1": True},
        train_after={"t1": True},
        ho_before={"h1": False},
        ho_after={"h1": True},
    )
    assert decision.accepted is True


def test_conservative_gate_rejects_no_op():
    """No change is not an improvement: reject rather than churn the main line."""
    decision = gate_case(
        gate="conservative",
        train_before={"t1": True},
        train_after={"t1": True},
        ho_before={"h1": False},
        ho_after={"h1": False},
    )
    assert decision.accepted is False
    assert "no split improved" in decision.reason


def test_conservative_gate_rejects_train_regression_even_with_holdout_gain():
    decision = gate_case(
        gate="conservative",
        train_before={"t1": True, "t2": True},
        train_after={"t1": True, "t2": False},
        ho_before={"h1": False, "h2": False},
        ho_after={"h1": True, "h2": True},
    )
    assert decision.accepted is False
    assert "train regressed" in decision.reason


def test_gate_reports_rate_deltas():
    decision = gate_case(
        gate="conservative",
        train_before={"t1": False, "t2": False},
        train_after={"t1": True, "t2": False},
        ho_before={"h1": True},
        ho_after={"h1": True},
    )
    assert decision.delta_in_rate == pytest.approx(0.5)
    assert decision.delta_ho_rate == pytest.approx(0.0)


def test_objective_gate_promotes_continuous_gain_without_a_pass_flip():
    current_train = make_split(variant="current", results={"a": False})
    current_holdout = make_split(variant="current", results={"b": False})
    candidate_train = replace(current_train, variant="candidate", score=0.6)
    candidate_holdout = replace(current_holdout, variant="candidate", score=0.7)
    decision = decide(
        gate="objective",
        goal=GoalContract(primary_metric="score"),
        current_train=current_train,
        current_holdout=current_holdout,
        candidate_train=candidate_train,
        candidate_holdout=candidate_holdout,
    )
    assert decision.accepted
    assert decision.delta_in == decision.delta_ho == 0
    assert decision.delta_ho_score == pytest.approx(0.7)


def test_objective_gate_rejects_pass_regression_even_when_score_rises():
    current_train = make_split(variant="current", results={"a": True})
    current_holdout = make_split(variant="current", results={"b": True})
    candidate_train = replace(current_train, variant="candidate", passed=0, score=2.0)
    candidate_holdout = replace(current_holdout, variant="candidate", score=2.0)
    decision = decide(
        gate="objective",
        goal=GoalContract(primary_metric="score", require_no_pass_regression=True),
        current_train=current_train,
        current_holdout=current_holdout,
        candidate_train=candidate_train,
        candidate_holdout=candidate_holdout,
    )
    assert not decision.accepted


def test_objective_gate_can_require_real_holdout_improvement():
    current_train = make_split(variant="current", results={"a": False})
    current_holdout = make_split(variant="current", results={"b": False})
    candidate_train = replace(current_train, variant="candidate", score=0.5)
    candidate_holdout = replace(current_holdout, variant="candidate", score=0.0)
    decision = decide(
        gate="objective",
        goal=GoalContract(
            primary_metric="score",
            min_delta=0.01,
            require_holdout_improvement=True,
        ),
        current_train=current_train,
        current_holdout=current_holdout,
        candidate_train=candidate_train,
        candidate_holdout=candidate_holdout,
    )

    assert not decision.accepted
    assert "holdout improvement required" in decision.reason


def test_objective_gate_accepts_holdout_gain_when_required():
    current_train = make_split(variant="current", results={"a": False})
    current_holdout = make_split(variant="current", results={"b": False})
    candidate_train = replace(current_train, variant="candidate", score=0.0)
    candidate_holdout = replace(current_holdout, variant="candidate", score=0.2)
    decision = decide(
        gate="objective",
        goal=GoalContract(
            primary_metric="score",
            min_delta=0.01,
            require_holdout_improvement=True,
        ),
        current_train=current_train,
        current_holdout=current_holdout,
        candidate_train=candidate_train,
        candidate_holdout=candidate_holdout,
    )

    assert decision.accepted


def test_invalid_gate_rejected():
    with pytest.raises(ValueError, match="invalid gate"):
        gate_case(
            gate="whatever",
            train_before={"t1": True},
            train_after={"t1": True},
            ho_before={"h1": True},
            ho_after={"h1": True},
        )


# --------------------------------------------------------------------------
# config surface
# --------------------------------------------------------------------------


CONFIG = """
[experiment]
name = "cfg"
runner = "pytest"
workspace_root = "{root}"
model = "m"
{extra}

[runner.pytest]
project_root = "{root}"

[surfaces.prompt]
kind = "module_attr"
target = "pkg.mod:PROMPT"
filename = "prompt.txt"
base_value = "hi"

[[cases]]
case_id = "tests/test_a.py::test_a"
split = "train"
stratum = "s"

[[cases]]
case_id = "tests/test_b.py::test_b"
split = "holdout"
stratum = "s"
"""


def write_config(tmp_path: Path, extra: str = "") -> Path:
    path = tmp_path / "config.toml"
    path.write_text(CONFIG.format(root=tmp_path.as_posix(), extra=extra))
    return path


def test_config_defaults_are_safe(tmp_path: Path):
    """A config that says nothing must still get 3 repeats and the conservative gate."""
    experiment = load_experiment(write_config(tmp_path))
    assert experiment.repeats == 3
    assert experiment.gate == "conservative"


def test_config_can_override(tmp_path: Path):
    experiment = load_experiment(write_config(tmp_path, extra='repeats = 5\ngate = "combined"'))
    assert experiment.repeats == 5
    assert experiment.gate == "combined"


def test_config_rejects_bad_values(tmp_path: Path):
    with pytest.raises(ValueError, match="repeats must be at least 1"):
        load_experiment(write_config(tmp_path, extra="repeats = 0"))
    with pytest.raises(ValueError, match="invalid gate"):
        load_experiment(write_config(tmp_path, extra='gate = "sum"'))
