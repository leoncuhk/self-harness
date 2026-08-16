"""Public exports for self-harness."""

from self_harness.apparatus import STATUS_APPARATUS, apparatus_kind, is_measurable
from self_harness.archive import ArchiveEntry, CandidateArchive
from self_harness.coding import CodingProjectRunner
from self_harness.contracts import GoalContract, MetricConstraint, load_goal_contract
from self_harness.core import (
    CaseOutcome,
    EvalCase,
    Experiment,
    FingerprintDriftError,
    Proposal,
    RunReport,
    SplitResult,
    Surface,
    Variant,
    check_fingerprint_discipline,
    load_experiment,
    main,
    run_experiment,
    validate_experiment,
)
from self_harness.cost import BudgetDecision, CostProfile, check_budget, profile_split
from self_harness.diagnostics import (
    DEFAULT_DIAGNOSTICS,
    DiagnosticContract,
    DiagnosticEvidence,
    FacetRule,
    collect_diagnostic_facets,
    load_diagnostic_contract,
)
from self_harness.gate import GateDecision, decide
from self_harness.guards import GuardReport, check_variant
from self_harness.ledger import (
    FlipReport,
    LedgerEntry,
    Prediction,
    compute_flips,
    parse_prediction,
    score_prediction,
    write_ledger,
)
from self_harness.measurement import (
    MatchedEstimate,
    MeasurementContract,
    load_measurement_contract,
    matched_question_estimate,
)
from self_harness.patching import (
    build_baseline_variant,
    build_variant,
    patch_from_env,
    patch_module_attrs,
    workspace_override_context,
)
from self_harness.repeats import aggregate_split_results, run_split_repeated
from self_harness.runners import (
    UnresolvedCaseError,
    parse_harbor_case,
    parse_pytest_outcomes,
    resolve_case_id,
)
from self_harness.signatures import (
    FailureCluster,
    FailureSignature,
    classify,
    cluster_failures,
    cluster_split,
    signature_histogram,
)

__all__ = [
    "DEFAULT_DIAGNOSTICS",
    "STATUS_APPARATUS",
    "ArchiveEntry",
    "BudgetDecision",
    "CandidateArchive",
    "CaseOutcome",
    "CodingProjectRunner",
    "CostProfile",
    "DiagnosticContract",
    "DiagnosticEvidence",
    "EvalCase",
    "Experiment",
    "FacetRule",
    "FailureCluster",
    "FailureSignature",
    "FingerprintDriftError",
    "FlipReport",
    "GateDecision",
    "GoalContract",
    "GuardReport",
    "LedgerEntry",
    "MatchedEstimate",
    "MeasurementContract",
    "MetricConstraint",
    "Prediction",
    "Proposal",
    "RunReport",
    "SplitResult",
    "Surface",
    "UnresolvedCaseError",
    "Variant",
    "aggregate_split_results",
    "apparatus_kind",
    "build_baseline_variant",
    "build_variant",
    "check_budget",
    "check_fingerprint_discipline",
    "check_variant",
    "classify",
    "cluster_failures",
    "cluster_split",
    "collect_diagnostic_facets",
    "compute_flips",
    "decide",
    "is_measurable",
    "load_diagnostic_contract",
    "load_experiment",
    "load_goal_contract",
    "load_measurement_contract",
    "main",
    "matched_question_estimate",
    "parse_harbor_case",
    "parse_prediction",
    "parse_pytest_outcomes",
    "patch_from_env",
    "patch_module_attrs",
    "profile_split",
    "resolve_case_id",
    "run_experiment",
    "run_split_repeated",
    "score_prediction",
    "signature_histogram",
    "validate_experiment",
    "workspace_override_context",
    "write_ledger",
]
