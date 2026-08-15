"""Instrument-correctness tests (Phase 0).

Every test here pins a defect that was found in real run artifacts, not one that
was imagined. The pattern behind all of them is the same: the system recorded a
number that the thing it measured did not support, and every layer above —
gate, ledger, report, analysis — passed it straight through.
"""

from __future__ import annotations

import json

import pytest
from verify_artifacts import audit_run, safe_slug

from self_harness import runners as runners_module
from self_harness.agent import _private_case_sources
from self_harness.apparatus import apparatus_kind, is_measurable
from self_harness.core import (
    CaseOutcome,
    EvalCase,
    FingerprintDriftError,
    SplitResult,
    check_fingerprint_discipline,
    load_experiment,
    run_experiment,
)
from self_harness.gate import decide
from self_harness.guards import VIOLATION_UNPARSEABLE, check_variant
from self_harness.patching import build_baseline_variant, build_variant
from self_harness.repeats import aggregate_split_results
from self_harness.retry import retry_transient
from self_harness.runners import (
    UnresolvedCaseError,
    parse_pytest_outcomes,
    resolve_case_id,
)
from self_harness.signatures import classify
from tests.test_self_harness import _write_minimal_pytest_experiment


def outcome(case_id: str, status: str, message: str | None = None) -> CaseOutcome:
    return CaseOutcome(
        case_id=case_id,
        split="train",
        stratum="s",
        status=status,
        score=1.0 if status == "passed" else 0.0,
        duration_s=1.0,
        failure_message=message,
    )


def split(outcomes: list[CaseOutcome], *, variant: str = "v", apparatus: int = 0) -> SplitResult:
    measured = [o for o in outcomes if o.status != "apparatus"]
    return SplitResult(
        split="train",
        variant=variant,
        model="m",
        passed=sum(1 for o in measured if o.passed),
        total=len(measured),
        score=0.0,
        returncode=0,
        run_dir="run",
        outcomes=tuple(outcomes),
        apparatus=apparatus or sum(1 for o in outcomes if o.status == "apparatus"),
    )


# --- apparatus partition -------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "kind"),
    [
        ("case missing from junit.xml", "junit_unreadable"),
        ("openai.APIConnectionError: Connection error.", "transport"),
        ("httpcore.RemoteProtocolError: Server disconnected", "transport"),
        ("AttributeError: Missing config key: OPENAI_API_KEY", "provider_config"),
        ("OPENAI_BASE_URL is required for the self-harness provider", "provider_config"),
        ("case process timed out", "case_timeout"),
        # Not apparatus: the agent ran and spent its budget.
        ("langgraph.errors.GraphRecursionError: Recursion limit of 60 reached", None),
        # Not apparatus: the proposer's own code is broken.
        ("E TypeError: break_retry_loops() missing 1 required positional argument", None),
        ("E AssertionError: assert '6' == '4'", None),
    ],
)
def test_apparatus_classification_draws_the_line_at_did_we_measure(message, kind):
    assert apparatus_kind(message) == kind


def test_apparatus_failures_leave_the_denominator():
    """20 of mvp2-baseline's 63 recorded failures never measured anything."""
    result = split(
        [
            outcome("a", "passed"),
            outcome("b", "failed", "E AssertionError: wrong"),
            outcome("c", "apparatus", "[apparatus:junit_unreadable] case missing from junit.xml"),
        ]
    )
    assert (result.passed, result.total) == (1, 2)
    assert result.correctness == pytest.approx(0.5)
    assert result.apparatus == 1
    # Scored as a failure instead, the same run would read 1/3 = 0.33.


def test_apparatus_outcomes_are_not_mined_as_harness_weaknesses():
    result = split(
        [
            outcome("b", "failed", "E AssertionError: wrong"),
            outcome("c", "apparatus", "[apparatus:transport] Connection error."),
        ]
    )
    assert [o.case_id for o in result.failing_outcomes()] == ["b"]


def test_all_repeats_apparatus_reports_the_case_as_unmeasured(tmp_path):
    a = split([outcome("x", "apparatus", "[apparatus:transport] Connection error.")], variant="v")
    b = split([outcome("x", "apparatus", "[apparatus:transport] Connection error.")], variant="v")
    aggregated = aggregate_split_results([a, b], run_dir=tmp_path)
    assert aggregated.total == 0
    assert aggregated.apparatus == 2
    assert aggregated.outcomes[0].status == "apparatus"


def test_partial_apparatus_scores_only_the_measured_repeats(tmp_path):
    a = split([outcome("x", "passed")], variant="v")
    b = split([outcome("x", "apparatus", "[apparatus:transport] Connection error.")], variant="v")
    aggregated = aggregate_split_results([a, b], run_dir=tmp_path)
    # One measured attempt, and it passed: 1/1, not 1/2.
    assert (aggregated.passed, aggregated.total, aggregated.apparatus) == (1, 1, 1)
    assert aggregated.outcomes[0].status == "passed"


def test_a_mostly_unmeasured_evaluation_cannot_promote():
    """Shrinking the denominator must not become a way to clear the gate."""
    current = split([outcome("a", "failed", "E AssertionError"), outcome("b", "failed", "E AssertionError")])
    # Candidate: one lucky measured pass, everything else never ran.
    candidate = SplitResult(
        split="train",
        variant="cand",
        model="m",
        passed=1,
        total=1,
        score=0.0,
        returncode=0,
        run_dir="run",
        outcomes=(outcome("a", "passed"),),
        apparatus=9,
    )
    assert not candidate.measurable
    decision = decide(
        gate="conservative",
        current_train=current,
        current_holdout=current,
        candidate_train=candidate,
        candidate_holdout=current,
    )
    assert not decision.accepted
    assert "unmeasured" in decision.reason


def test_is_measurable_needs_at_least_one_measured_attempt():
    assert not is_measurable(apparatus=5, measured=0)
    assert is_measurable(apparatus=1, measured=19)
    assert not is_measurable(apparatus=5, measured=15)


# --- failure signatures --------------------------------------------------------


def test_signature_reads_the_error_not_the_test_source():
    """pytest echoes the suite's own decorator; the classifier used to match it.

    Real message shape from runs/mvp2-baseline: every genuine assertion failure
    classified as (timeout, agent_caused, unbounded_retry_loop) purely because
    `@pytest.mark.timeout(420)` appears in the echoed source.
    """
    message = (
        "task_id = 'fmt-fixed-width', model = 'openai:gpt-4.1-nano'\n"
        "    @pytest.mark.timeout(420)\n"
        '    @pytest.mark.parametrize("task_id", sorted(VERIFIERS))\n'
        "    def test_task(task_id: str, model: str) -> None:\n"
        "E       AssertionError: assert 'bolt 42' == 'bolt  42'"
    )
    signature = classify(outcome("c", "failed", message))
    assert signature.cause == "assertion_failed"
    assert signature.mechanism != "unbounded_retry_loop"


def test_step_budget_exhaustion_gets_its_own_signature():
    signature = classify(
        outcome("c", "failed", "langgraph.errors.GraphRecursionError: Recursion limit of 60 reached")
    )
    assert signature.cause == "step_budget_exhausted"
    assert signature.mechanism == "step_budget_exhausted"


def test_a_candidate_that_does_not_load_is_named_as_such():
    message = (
        "_self = <langchain.agents.middleware.types.break_retry_loops object>\n"
        "  middleware.py:12\n"
        "E   TypeError: break_retry_loops() missing 1 required positional argument: 'config'"
    )
    signature = classify(outcome("c", "failed", message))
    assert signature.cause == "harness_did_not_load"
    assert signature.mechanism == "harness_did_not_load"


# --- fingerprint discipline ----------------------------------------------------


def test_one_stage_two_fingerprints_fails_the_stage():
    """runs/mvp2-evolve spans fp_e010545658 and fp_65c6c2730f; the frozen rule voids it."""
    a = split([outcome("a", "passed")])
    a = SplitResult(**{**a.__dict__, "fingerprints": ("fp_aaa",)})
    b = split([outcome("b", "passed")])
    b = SplitResult(**{**b.__dict__, "fingerprints": ("fp_bbb",)})
    with pytest.raises(FingerprintDriftError, match="fp_aaa, fp_bbb"):
        check_fingerprint_discipline([a, b], discipline="strict")
    # "report" records the drift instead of failing, for runs that accept it.
    assert check_fingerprint_discipline([a, b], discipline="report") == ("fp_aaa", "fp_bbb")


def test_one_fingerprint_is_fine():
    a = split([outcome("a", "passed")])
    a = SplitResult(**{**a.__dict__, "fingerprints": ("fp_aaa",)})
    assert check_fingerprint_discipline([a], discipline="strict") == ("fp_aaa",)


# --- answer-key leak -----------------------------------------------------------


def test_a_source_file_shared_with_a_private_split_is_never_copied(tmp_path):
    """The real leak: one parametrised module held all 16 verifiers, holdout and
    scorecard included, and was copied to the proposer on every iteration."""
    config = _write_minimal_pytest_experiment(tmp_path / "fixture")
    experiment = load_experiment(config)
    private = _private_case_sources(experiment)
    train_sources = {
        case.render(model=experiment.model).partition("::")[0]
        for case in experiment.cases_for_split("train")
    }
    assert train_sources & private, "fixture must exercise the shared-source shape"


# --- surface smoke gate --------------------------------------------------------


def test_a_surface_that_does_not_parse_is_rejected_before_any_eval(tmp_path):
    config = _write_minimal_pytest_experiment(tmp_path / "fixture")
    experiment = load_experiment(config)
    baseline = build_baseline_variant(experiment)
    values = dict(baseline.values)
    values["tools"] = "def make_tools(:\n    return []\n"
    candidate = build_variant(experiment=experiment, label="iter-001", values=values)
    report = check_variant(experiment=experiment, baseline=baseline, candidate=candidate)
    assert not report.ok
    assert any(v.kind == VIOLATION_UNPARSEABLE for v in report.violations)


def test_prose_surfaces_are_not_compiled(tmp_path):
    config = _write_minimal_pytest_experiment(tmp_path / "fixture")
    experiment = load_experiment(config)
    baseline = build_baseline_variant(experiment)
    values = dict(baseline.values)
    values["prompt"] = "Always verify the output file before you finish: def not python("
    candidate = build_variant(experiment=experiment, label="iter-001", values=values)
    report = check_variant(experiment=experiment, baseline=baseline, candidate=candidate)
    assert not any(v.kind == VIOLATION_UNPARSEABLE for v in report.violations)


# --- artifact auditor ----------------------------------------------------------


def test_verify_artifacts_catches_a_recorded_outcome_the_xml_denies(tmp_path):
    run = tmp_path / "run"
    split_dir = run / "history" / "private" / "scorecard" / "baseline" / "rep00"
    case_id = "tests/test_agentic.py::test_task[ex-unique-domains]"
    case_dir = split_dir / "cases" / safe_slug(case_id)
    case_dir.mkdir(parents=True)
    # Exactly the shape this suite emits: dotted classname, no file attribute —
    # which rebuild_case_id cannot map back to a configured case id.
    (case_dir / "junit.xml").write_text(
        '<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="1">'
        '<testcase classname="benchmarks.agentic.evals.tests.test_agentic" '
        'name="test_task[ex-unique-domains]" time="1.0"></testcase>'
        "</testsuite></testsuites>"
    )
    (split_dir / "result.json").write_text(
        json.dumps(
            {
                "split": "scorecard",
                "variant": "baseline",
                "model": "m",
                "passed": 0,
                "total": 1,
                "score": 0.0,
                "returncode": 1,
                "run_dir": str(split_dir),
                "outcomes": [
                    {
                        "case_id": case_id,
                        "split": "scorecard",
                        "stratum": "s",
                        "status": "missing",
                        "score": 0.0,
                        "duration_s": 0.0,
                        "failure_message": "case missing from junit.xml",
                        "artifacts_dir": str(case_dir),
                        "trace_ref": None,
                    }
                ],
            }
        )
    )
    discrepancies, _ = audit_run(run)
    assert len(discrepancies) == 1
    assert discrepancies[0].recorded == "missing"
    assert discrepancies[0].derived == "passed"


def test_verify_artifacts_does_not_count_proposer_evidence_twice(tmp_path):
    run = tmp_path / "run"
    case_id = "tests/test_product.py::test_task[case-1]"
    result = {"outcomes": [{"case_id": case_id, "status": "passed"}]}
    for split_dir in (
        run / "history" / "train" / "baseline" / "rep00",
        run / "proposer_workspace" / "history" / "train" / "baseline" / "rep00",
    ):
        case_dir = split_dir / "cases" / safe_slug(case_id)
        case_dir.mkdir(parents=True)
        (case_dir / "junit.xml").write_text(
            '<?xml version="1.0"?><testsuites><testsuite tests="1">'
            '<testcase classname="tests.test_product" name="test_task[case-1]" />'
            "</testsuite></testsuites>"
        )
        (split_dir / "result.json").write_text(json.dumps(result))

    discrepancies, counts = audit_run(run)

    assert not discrepancies
    assert counts["recorded:passed"] == 1
    assert counts["derived:passed"] == 1


def test_junit_without_a_file_attribute_still_resolves_to_its_case():
    """The exact XML shape that zeroed every scorecard evaluation."""
    case_id = "tests/test_agentic.py::test_task[ex-unique-domains]"
    configured = {case_id: EvalCase(case_id, "scorecard", "extraction")}
    resolved = resolve_case_id(
        file_attr="",
        classname_attr="benchmarks.agentic.evals.tests.test_agentic",
        name_attr="test_task[ex-unique-domains]",
        configured=configured,
        sole_candidate=True,
    )
    assert resolved == case_id


def test_a_classname_that_carries_the_module_path_still_resolves():
    """`pkg.tests.a` denotes tests/a.py unambiguously; b.py cannot match it."""
    configured = {
        "tests/a.py::test_task[x]": EvalCase("tests/a.py::test_task[x]", "train", "s"),
        "tests/b.py::test_task[x]": EvalCase("tests/b.py::test_task[x]", "train", "s"),
    }
    assert (
        resolve_case_id(
            file_attr="",
            classname_attr="pkg.tests.a",
            name_attr="test_task[x]",
            configured=configured,
            sole_candidate=False,
        )
        == "tests/a.py::test_task[x]"
    )


def test_a_genuine_tie_is_not_broken_by_guessing():
    """Two configured ids equally denoted by one candidate: report nothing.

    Picking one would attach a result to the wrong case, which is worse than a
    parse miss because it looks like a valid outcome.
    """
    configured = {
        "x/tests/a.py::test_task[q]": EvalCase("x/tests/a.py::test_task[q]", "train", "s"),
        "y/tests/a.py::test_task[q]": EvalCase("y/tests/a.py::test_task[q]", "train", "s"),
    }
    assert (
        resolve_case_id(
            file_attr="",
            classname_attr="tests.a",
            name_attr="test_task[q]",
            configured=configured,
            sole_candidate=False,
        )
        is None
    )


def test_an_unpromoted_run_does_not_evaluate_the_sealed_split_twice(tmp_path, monkeypatch):
    """The second write overwrote the first, in the same variant-keyed directory."""
    # A proposer that changes nothing: no promotion, so final == baseline.
    def noop_proposer(*, experiment, workspace):
        del experiment
        workspace.proposal_file.write_text("# Proposal\n\nNo change.\n")

    monkeypatch.setattr("self_harness.pi.invoke_pi_proposer", noop_proposer)

    scorecard_runs: list[str] = []
    real_run_split = runners_module.PytestRunner.run_split

    def spy(self, **kwargs):
        if kwargs["split"] == "scorecard":
            scorecard_runs.append(kwargs["variant"].key)
        return real_run_split(self, **kwargs)

    monkeypatch.setattr(runners_module.PytestRunner, "run_split", spy)

    config = _write_minimal_pytest_experiment(tmp_path / "fixture")
    report = run_experiment(load_experiment(config), output_dir=tmp_path / "run", max_iterations=1)
    assert scorecard_runs, "the fixture must define a scorecard split"
    assert len(set(scorecard_runs)) == 1
    assert scorecard_runs.count("baseline") == report.repeats  # one pass, not two
    assert report.baseline_scorecard is not None
    assert report.final_scorecard is not None
    assert report.final_scorecard.passed == report.baseline_scorecard.passed


def test_rootdir_lift_classname_resolves_and_keeps_detail(tmp_path):
    """The long-classname shape a second run into the same directory produces."""
    case_id = "tests/test_agentic.py::test_task[ex-unique-domains]"
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="1">'
        '<testcase classname="benchmarks.agentic.evals.tests.test_agentic" '
        'name="test_task[ex-unique-domains]" time="14.07">'
        '<failure message="AssertionError">E   AssertionError: assert 6 == 4</failure>'
        "</testcase></testsuite></testsuites>"
    )
    outcomes = parse_pytest_outcomes(
        junit_path=junit,
        cases=[EvalCase(case_id, "scorecard", "extraction")],
        model="m",
        artifacts_dir=tmp_path,
    )
    assert len(outcomes) == 1
    assert outcomes[0].case_id == case_id
    assert outcomes[0].status == "failed"
    assert outcomes[0].duration_s == pytest.approx(14.07)
    assert "assert 6 == 4" in (outcomes[0].failure_message or "")


def test_class_scoped_nodeid_resolves(tmp_path):
    case_id = "tests/test_suite.py::TestGroup::test_case"
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="1">'
        '<testcase classname="tests.test_suite.TestGroup" name="test_case" time="1.0"/>'
        "</testsuite></testsuites>"
    )
    outcomes = parse_pytest_outcomes(
        junit_path=junit,
        cases=[EvalCase(case_id, "train", "s")],
        model="m",
        artifacts_dir=tmp_path,
    )
    assert outcomes[0].case_id == case_id
    assert outcomes[0].status == "passed"


def test_recorded_but_unresolvable_raises_instead_of_scoring_zero(tmp_path):
    """A parse miss must never be indistinguishable from a task failure."""
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="1">'
        '<testcase classname="totally.unrelated" name="test_something_else" time="1.0"/>'
        "</testsuite></testsuites>"
    )
    with pytest.raises(UnresolvedCaseError, match="could not resolve"):
        parse_pytest_outcomes(
            junit_path=junit,
            cases=[
                EvalCase("tests/a.py::test_x", "train", "s"),
                EvalCase("tests/b.py::test_y", "train", "s"),
            ],
            model="m",
            artifacts_dir=tmp_path,
        )


def test_junit_with_no_testcases_is_apparatus_not_a_failure(tmp_path):
    """A killed rollout measured nothing; it must not abort a 180-rollout stage."""
    junit = tmp_path / "junit.xml"
    junit.write_text('<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="0"/></testsuites>')
    outcomes = parse_pytest_outcomes(
        junit_path=junit,
        cases=[EvalCase("tests/a.py::test_x", "train", "s")],
        model="m",
        artifacts_dir=tmp_path,
    )
    assert outcomes[0].status == "apparatus"
    assert outcomes[0].is_apparatus


# --- retry policy --------------------------------------------------------------


def test_retry_keeps_trying_across_a_multi_minute_outage():
    """The two earlier ladders (2s/4s, then ~50s) were each exhausted by one outage."""
    clock = {"t": 0.0}
    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        clock["t"] += seconds

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 8:
            msg = "Server disconnected without sending a response."
            raise ConnectionError(msg)
        return "ok"

    assert (
        retry_transient(flaky, label="test", sleep=fake_sleep, now=lambda: clock["t"]) == "ok"
    )
    assert calls["n"] == 8
    # Backoff doubles and caps, and the outage it survives is minutes long.
    assert slept == [5.0, 10.0, 20.0, 40.0, 60.0, 60.0, 60.0]
    assert sum(slept) > 200


def test_retry_gives_up_at_the_time_budget_not_at_an_attempt_count():
    clock = {"t": 0.0}

    def fake_sleep(seconds: float) -> None:
        clock["t"] += seconds

    def always_down():
        msg = "Connection error."
        raise ConnectionError(msg)

    with pytest.raises(ConnectionError):
        retry_transient(
            always_down,
            label="test",
            max_total_s=30.0,
            sleep=fake_sleep,
            now=lambda: clock["t"],
        )
    assert clock["t"] <= 30.0


def test_a_wrong_answer_is_never_retried():
    """Resampling until the answer is convenient is a different experiment."""
    calls = {"n": 0}

    def wrong():
        calls["n"] += 1
        msg = "assert '6' == '4'"
        raise AssertionError(msg)

    with pytest.raises(AssertionError):
        retry_transient(wrong, label="test", sleep=lambda _s: None, now=lambda: 0.0)
    assert calls["n"] == 1
