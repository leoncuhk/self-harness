"""Public exports for better-harness."""

from better_harness.apparatus import STATUS_APPARATUS, apparatus_kind, is_measurable
from better_harness.archive import ArchiveEntry, CandidateArchive
from better_harness.coding import CodingProjectRunner
from better_harness.contracts import GoalContract, MetricConstraint, load_goal_contract
from better_harness.core import (
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
from better_harness.cost import BudgetDecision, CostProfile, check_budget, profile_split
from better_harness.gate import GateDecision, decide
from better_harness.guards import GuardReport, check_variant
from better_harness.ledger import (
    FlipReport,
    LedgerEntry,
    Prediction,
    compute_flips,
    parse_prediction,
    score_prediction,
    write_ledger,
)
from better_harness.patching import (
    build_baseline_variant,
    build_variant,
    patch_from_env,
    patch_module_attrs,
    workspace_override_context,
)
from better_harness.repeats import aggregate_split_results, run_split_repeated
from better_harness.runners import (
    UnresolvedCaseError,
    parse_harbor_case,
    parse_pytest_outcomes,
    resolve_case_id,
)
from better_harness.signatures import (
    FailureCluster,
    FailureSignature,
    classify,
    cluster_failures,
    cluster_split,
    signature_histogram,
)

__all__ = [
    "STATUS_APPARATUS",
    "ArchiveEntry",
    "BudgetDecision",
    "CandidateArchive",
    "CaseOutcome",
    "CodingProjectRunner",
    "CostProfile",
    "EvalCase",
    "Experiment",
    "FailureCluster",
    "FailureSignature",
    "FingerprintDriftError",
    "FlipReport",
    "GateDecision",
    "GoalContract",
    "GuardReport",
    "LedgerEntry",
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
    "compute_flips",
    "decide",
    "is_measurable",
    "load_experiment",
    "load_goal_contract",
    "main",
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
