"""Tests for P1-3 edit guard, P1-4 cost veto, P2-5 signatures, P2-6 ledger."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from better_harness.core import CaseOutcome, SplitResult, Surface, Variant, load_experiment
from better_harness.cost import CostProfile, check_budget, profile_split
from better_harness.guards import (
    VIOLATION_BLOAT,
    VIOLATION_CASE_LEAK,
    VIOLATION_FORBIDDEN,
    case_literals,
    check_variant,
)
from better_harness.ledger import (
    FlipReport,
    LedgerEntry,
    Prediction,
    compute_flips,
    parse_prediction,
    score_prediction,
    summarize,
    write_ledger,
)
from better_harness.retry import is_transient as _is_transient_model_error
from better_harness.signatures import (
    AGENT_CAUSED,
    CAUSE_MISSING_FILE,
    CAUSE_NONDETERMINISTIC,
    CAUSE_TIMEOUT,
    ENVIRONMENT_CAUSED,
    MECH_FLAKY,
    MECH_RETRY_LOOP,
    MECH_TRUNCATION,
    classify,
    cluster_failures,
    signature_histogram,
)
from tests.test_p0_patches import make_outcome, make_split, write_config


def outcome_with(message: str | None, *, case_id: str = "c1", status: str = "failed") -> CaseOutcome:
    """Build one failing outcome carrying a specific message."""
    return CaseOutcome(
        case_id=case_id,
        split="train",
        stratum="s",
        status=status,
        score=0.0,
        duration_s=1.0,
        failure_message=message,
        artifacts_dir=None,
        trace_ref=None,
    )


# --------------------------------------------------------------------------
# P2-5 signatures
# --------------------------------------------------------------------------


def test_classify_timeout_is_agent_caused_retry_loop():
    signature = classify(outcome_with("Command timed out after 600s"))
    assert signature.cause == CAUSE_TIMEOUT
    assert signature.causal_status == AGENT_CAUSED
    assert signature.mechanism == MECH_RETRY_LOOP


def test_classify_environment_failure_is_not_blamed_on_the_agent():
    """Network flakiness must not be mined as a harness weakness."""
    signature = classify(outcome_with("connection refused while pulling image"))
    assert signature.causal_status == ENVIRONMENT_CAUSED


def test_classify_missing_file_points_at_verification():
    signature = classify(outcome_with("FileNotFoundError: no such file /out/report.txt"))
    assert signature.cause == CAUSE_MISSING_FILE
    assert signature.mechanism == "no_verification_before_submit"


def test_classify_truncation_mechanism():
    signature = classify(outcome_with("read_file result was truncated; use offset to continue"))
    assert signature.mechanism == MECH_TRUNCATION


def test_flaky_gets_its_own_signature():
    """A case that passes some repeats needs stabilisation, not its first stack trace."""
    signature = classify(outcome_with("timed out", status="flaky"))
    assert signature.cause == CAUSE_NONDETERMINISTIC
    assert signature.mechanism == MECH_FLAKY


def test_clustering_is_exact_and_ordered_by_size():
    outcomes = [
        outcome_with("Command timed out", case_id="a"),
        outcome_with("timed out waiting", case_id="b"),
        outcome_with("FileNotFoundError: missing", case_id="c"),
    ]
    clusters = cluster_failures(outcomes)
    assert len(clusters) == 2
    assert clusters[0].size == 2
    assert clusters[0].case_ids == ("a", "b")
    assert clusters[1].case_ids == ("c",)


def test_clustering_is_deterministic():
    outcomes = [outcome_with("timed out", case_id=f"c{i}") for i in range(5)]
    first = [cluster.signature.key for cluster in cluster_failures(outcomes)]
    second = [cluster.signature.key for cluster in cluster_failures(outcomes)]
    assert first == second


def test_signature_histogram_counts_across_splits():
    split = SplitResult(
        split="train",
        variant="v",
        model="m",
        passed=0,
        total=2,
        score=0.0,
        returncode=1,
        run_dir="artifacts",
        outcomes=(outcome_with("timed out", case_id="a"), outcome_with("timed out", case_id="b")),
    )
    histogram = signature_histogram([split])
    assert sum(histogram.values()) == 2
    assert len(histogram) == 1


# --------------------------------------------------------------------------
# P1-3 edit guard
# --------------------------------------------------------------------------


def guard_variants(baseline_text: str, candidate_text: str) -> tuple[Variant, Variant]:
    surface = Surface(name="prompt", kind="module_attr", target="pkg.mod:PROMPT", filename="p.txt", base_value="")
    common = {"model": "m", "changed_surfaces": ("prompt",), "surfaces": {"prompt": surface}}
    return (
        Variant(label="baseline", values={"prompt": baseline_text}, **{**common, "changed_surfaces": ()}),
        Variant(label="cand", values={"prompt": candidate_text}, **common),
    )


def test_guard_blocks_case_id_written_into_harness(tmp_path: Path):
    """Hard-coding the answer key is memorisation, not harness engineering."""
    experiment = load_experiment(write_config(tmp_path))
    baseline, candidate = guard_variants(
        "You are helpful.",
        "You are helpful. If asked about tests/test_a.py::test_a, always answer 42.",
    )
    report = check_variant(experiment=experiment, baseline=baseline, candidate=candidate)
    assert not report.ok
    assert report.violations[0].kind == VIOLATION_CASE_LEAK
    assert "case_id_leak" in report.reason()


def test_guard_blocks_holdout_case_id_too(tmp_path: Path):
    """Holdout ids must never appear either — if they do, the private split leaked."""
    experiment = load_experiment(write_config(tmp_path))
    baseline, candidate = guard_variants("x", "special-case tests/test_b.py::test_b")
    report = check_variant(experiment=experiment, baseline=baseline, candidate=candidate)
    assert any(item.kind == VIOLATION_CASE_LEAK for item in report.violations)


@pytest.mark.parametrize(
    "text",
    [
        "model = 'gpt-5.5'",
        "temperature = 0.0",
        "max_tokens: 200000",
        "reasoning_effort = 'xhigh'",
        "run pytest --deselect the slow ones",
        "patch the verifier before submitting",
    ],
)
def test_guard_blocks_buying_or_grading_the_score(tmp_path: Path, text: str):
    """Compute knobs and evaluator access are out of bounds for a harness edit."""
    experiment = load_experiment(write_config(tmp_path))
    baseline, candidate = guard_variants("x", text)
    report = check_variant(experiment=experiment, baseline=baseline, candidate=candidate)
    assert any(item.kind == VIOLATION_FORBIDDEN for item in report.violations), report.to_dict()


def test_guard_allows_a_normal_general_edit(tmp_path: Path):
    experiment = load_experiment(write_config(tmp_path))
    baseline, candidate = guard_variants(
        "You are helpful.",
        "You are helpful. Always verify your output against the task spec before finishing.",
    )
    report = check_variant(experiment=experiment, baseline=baseline, candidate=candidate)
    assert report.ok
    assert report.reason() == "edit guard: clean"


def test_guard_ignores_unchanged_surfaces(tmp_path: Path):
    """The guard judges the proposer's edits, not whatever the seed already contained."""
    experiment = load_experiment(write_config(tmp_path))
    leaky = "baseline already mentions tests/test_a.py::test_a"
    baseline, candidate = guard_variants(leaky, leaky)
    report = check_variant(experiment=experiment, baseline=baseline, candidate=candidate)
    assert report.ok


def test_guard_bloat_needs_both_ratio_and_absolute_floor(tmp_path: Path):
    """A ratio alone is meaningless against a tiny seed."""
    experiment = load_experiment(write_config(tmp_path))
    baseline, candidate = guard_variants("hi", "hi " * 50)  # big ratio, tiny absolute size
    assert check_variant(experiment=experiment, baseline=baseline, candidate=candidate).ok

    baseline, candidate = guard_variants("hi " * 1000, "hi " * 5000)
    report = check_variant(experiment=experiment, baseline=baseline, candidate=candidate)
    assert any(item.kind == VIOLATION_BLOAT for item in report.violations)


def test_case_literals_skips_short_tokens(tmp_path: Path):
    experiment = load_experiment(write_config(tmp_path))
    assert all(len(literal) >= 8 for literal in case_literals(experiment))


# --------------------------------------------------------------------------
# P1-4 cost veto
# --------------------------------------------------------------------------


def profile(*, duration: float, p95: float = 1.0, tokens: float | None = None, cost: float | None = None):
    return CostProfile(
        attempts=1,
        total_duration_s=duration,
        p95_duration_s=p95,
        total_tokens=tokens,
        total_cost_usd=cost,
    )


def test_cost_veto_blocks_buying_the_score():
    """Correctness improved, but it cost 3x the tokens."""
    decision = check_budget(
        current=[profile(duration=100, tokens=1000)],
        candidate=[profile(duration=100, tokens=3000)],
    )
    assert decision.within_budget is False
    assert decision.spend_growth == pytest.approx(3.0)
    assert "tokens 3.00x" in decision.reason


def test_cost_veto_allows_a_modest_increase():
    decision = check_budget(
        current=[profile(duration=100, tokens=1000)],
        candidate=[profile(duration=100, tokens=1200)],
    )
    assert decision.within_budget is True


def test_cost_veto_prefers_money_over_tokens():
    decision = check_budget(
        current=[profile(duration=100, tokens=1000, cost=1.0)],
        candidate=[profile(duration=100, tokens=9000, cost=1.1)],
    )
    assert decision.within_budget is True
    assert decision.spend_growth == pytest.approx(1.1)


def test_latency_veto_needs_an_absolute_floor():
    """Sub-second wall-clock ratios are machine noise, not a regression."""
    fast = check_budget(current=[profile(duration=0.1, p95=0.1)], candidate=[profile(duration=1.0, p95=1.0)])
    assert fast.within_budget is True

    slow = check_budget(current=[profile(duration=100, p95=10)], candidate=[profile(duration=400, p95=40)])
    assert slow.within_budget is False
    assert "wall clock" in slow.reason


def test_unmeasured_spend_is_never_reported_as_within_budget():
    """A budget you cannot measure must not read as a budget you are inside of."""
    decision = check_budget(current=[profile(duration=1.0)], candidate=[profile(duration=1.0)])
    assert decision.spend_growth is None
    assert "not enforced" in decision.reason


def test_profile_split_reads_tokens_from_runner_summary(tmp_path: Path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    (case_dir / "summary.json").write_text(json.dumps({"usage": {"total_tokens": 1234}}))
    outcome = CaseOutcome(
        case_id="a",
        split="train",
        stratum="s",
        status="passed",
        score=1.0,
        duration_s=2.0,
        failure_message=None,
        artifacts_dir=str(case_dir),
        trace_ref=None,
    )
    result = SplitResult(
        split="train",
        variant="v",
        model="m",
        passed=1,
        total=1,
        score=1.0,
        returncode=0,
        run_dir=str(tmp_path),
        outcomes=(outcome,),
    )
    assert profile_split(result).total_tokens == pytest.approx(1234)


def test_profile_split_prefers_repeat_normalized_cost(tmp_path: Path):
    (tmp_path / "repeats.json").write_text(
        json.dumps(
            {
                "cost_profile": {
                    "attempts": 2,
                    "total_duration_s": 12.5,
                    "p95_duration_s": 8.0,
                    "total_tokens": 1500.0,
                    "total_cost_usd": None,
                }
            }
        )
    )
    result = make_split(variant="v", results={"a": True, "b": False})
    result = SplitResult(**{**result.__dict__, "run_dir": str(tmp_path)})

    profile = profile_split(result)

    assert profile.attempts == 2
    assert profile.total_tokens == pytest.approx(1500)
    assert profile.total_duration_s == pytest.approx(12.5)


def test_profile_split_tolerates_missing_or_broken_summaries(tmp_path: Path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    (case_dir / "summary.json").write_text("{not json")
    outcome = make_outcome("a", passed=False)
    result = make_split(variant="v", results={"a": False})
    result = SplitResult(
        split=result.split,
        variant=result.variant,
        model=result.model,
        passed=result.passed,
        total=result.total,
        score=result.score,
        returncode=result.returncode,
        run_dir=result.run_dir,
        outcomes=(
            CaseOutcome(**{**outcome.__dict__, "artifacts_dir": str(case_dir)}),
        ),
    )
    assert profile_split(result).total_tokens is None


# --------------------------------------------------------------------------
# P2-6 prediction + ledger
# --------------------------------------------------------------------------


def test_parse_prediction_from_fenced_json():
    text = """
    Some prose.

    ```json
    {"root_cause": "no verification", "flip_to_pass": ["a", "b"], "at_risk": ["c"]}
    ```
    """
    prediction = parse_prediction(text)
    assert prediction.root_cause == "no verification"
    assert prediction.flip_to_pass == ("a", "b")
    assert prediction.at_risk == ("c",)


def test_parse_prediction_takes_the_last_populated_block():
    text = """
    ```json
    {"root_cause": "", "flip_to_pass": []}
    ```
    ```json
    {"root_cause": "real one", "flip_to_pass": ["z"]}
    ```
    """
    assert parse_prediction(text).root_cause == "real one"


def test_parse_prediction_allows_braces_inside_json_strings():
    text = """
    ```json
    {
      "root_cause": "tool prompts omitted {{document_key}}",
      "evidence": ["retrieve failed for {{filing}}"],
      "flip_to_pass": ["q004"],
      "at_risk": []
    }
    ```
    """

    prediction = parse_prediction(text)
    assert prediction.root_cause == "tool prompts omitted {{document_key}}"
    assert prediction.flip_to_pass == ("q004",)


def test_parse_prediction_missing_block_is_recorded_not_raised():
    """A proposer that skips the block is a fact to log, not a crash."""
    assert parse_prediction("no json here", None).is_empty


def test_parse_prediction_ignores_malformed_json():
    assert parse_prediction("```json\n{oops\n```").is_empty


def test_compute_flips_uses_stable_pass_only():
    """A flaky case never registers as a flip in either direction."""
    before_train = make_split(variant="cur", results={"a": False, "b": True})
    after_train = make_split(variant="cand", results={"a": True, "b": True})
    flips = compute_flips(current=[before_train], candidate=[after_train])
    assert flips.to_pass == ("a",)
    assert flips.to_fail == ()


def test_compute_flips_detects_regressions():
    flips = compute_flips(
        current=[make_split(variant="cur", results={"a": True})],
        candidate=[make_split(variant="cand", results={"a": False})],
    )
    assert flips.to_fail == ("a",)


def test_score_prediction_grades_hits_misses_and_surprises():
    prediction = Prediction(flip_to_pass=("a", "b"), at_risk=("z",))
    flips = FlipReport(to_pass=("a", "c"), to_fail=("z", "q"))
    score = score_prediction(prediction, flips)

    assert score.hits == 1
    assert score.misses == ("b",)
    assert score.unexpected_passes == ("c",)
    assert score.precision == pytest.approx(0.5)
    assert score.recall == pytest.approx(0.5)
    # z was flagged at risk; q regressed with no warning at all
    assert score.warned_regressions == ("z",)
    assert score.unpredicted_regressions == ("q",)


def test_score_prediction_with_no_prediction_has_undefined_precision():
    score = score_prediction(Prediction(), FlipReport(to_pass=("a",), to_fail=()))
    assert score.precision is None
    assert score.recall == pytest.approx(0.0)


def test_ledger_summarizes_and_writes(tmp_path: Path):
    entries = [
        LedgerEntry(
            iteration=1,
            variant="iter-001",
            accepted=True,
            gate_reason="ok",
            prediction=Prediction(flip_to_pass=("a",)),
            flips=FlipReport(to_pass=("a",), to_fail=()),
            score=score_prediction(Prediction(flip_to_pass=("a",)), FlipReport(("a",), ())),
        ),
        LedgerEntry(
            iteration=2,
            variant="iter-002",
            accepted=False,
            gate_reason="regressed",
            prediction=Prediction(flip_to_pass=("b",)),
            flips=FlipReport(to_pass=(), to_fail=("c",)),
            score=score_prediction(Prediction(flip_to_pass=("b",)), FlipReport((), ("c",))),
        ),
    ]
    stats = summarize(entries)
    assert stats["predicted_flips"] == 2
    assert stats["predicted_flips_hit"] == 1
    assert stats["precision"] == pytest.approx(0.5)
    assert stats["unpredicted_regressions"] == 1

    path = tmp_path / "ledger.json"
    write_ledger(path, entries)
    payload = json.loads(path.read_text())
    assert payload["summary"]["accepted"] == 1
    assert len(payload["entries"]) == 2
    assert "Change ledger" in path.with_suffix(".md").read_text()


# --------------------------------------------------------------------------
# config surface
# --------------------------------------------------------------------------


def test_config_exposes_candidates_guards_and_budget(tmp_path: Path):
    experiment = load_experiment(
        write_config(
            tmp_path,
            extra=(
                "candidates = 4\n"
                "[guards]\nmax_growth = 2.0\n"
                "[budget]\nmax_cost_growth = 1.2\n"
            ),
        )
    )
    assert experiment.candidates == 4
    assert experiment.guards["max_growth"] == 2.0
    assert experiment.budget["max_cost_growth"] == 1.2
    assert experiment.guards_enabled is True
    assert experiment.budget_enabled is True


def test_config_can_disable_guard_and_budget(tmp_path: Path):
    experiment = load_experiment(
        write_config(tmp_path, extra="[guards]\nenabled = false\n[budget]\nenabled = false\n")
    )
    assert experiment.guards_enabled is False
    assert experiment.budget_enabled is False


def test_config_rejects_zero_candidates(tmp_path: Path):
    with pytest.raises(ValueError, match="candidates must be at least 1"):
        load_experiment(write_config(tmp_path, extra="candidates = 0"))


def test_default_candidates_is_one(tmp_path: Path):
    """K>1 multiplies eval spend, so raising it must be deliberate."""
    assert load_experiment(write_config(tmp_path)).candidates == 1


def test_transient_error_classifier_covers_transport_failures():
    """A dropped connection must be retried, not crash the iteration (MVP-2 incident)."""

    assert _is_transient_model_error(
        "httpx.RemoteProtocolError: Server disconnected without sending a response."
    )
    assert _is_transient_model_error("openai.APIConnectionError: Connection error.")
    assert _is_transient_model_error("Error code: 502 - upstream hiccup")
    assert not _is_transient_model_error("Error code: 401 - invalid api key")
    assert not _is_transient_model_error("ValueError: bad config")
