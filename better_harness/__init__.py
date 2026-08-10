"""Public exports for better-harness."""

from better_harness.core import (
    CaseOutcome,
    EvalCase,
    Experiment,
    Proposal,
    RunReport,
    SplitResult,
    Surface,
    Variant,
    load_experiment,
    main,
    run_experiment,
    validate_experiment,
)
from better_harness.gate import GateDecision, decide
from better_harness.patching import (
    build_baseline_variant,
    build_variant,
    patch_from_env,
    patch_module_attrs,
    workspace_override_context,
)
from better_harness.repeats import aggregate_split_results, run_split_repeated
from better_harness.runners import parse_harbor_case, parse_pytest_outcomes

__all__ = [
    "CaseOutcome",
    "EvalCase",
    "Experiment",
    "GateDecision",
    "Proposal",
    "RunReport",
    "SplitResult",
    "Surface",
    "Variant",
    "aggregate_split_results",
    "build_baseline_variant",
    "build_variant",
    "decide",
    "load_experiment",
    "main",
    "parse_harbor_case",
    "parse_pytest_outcomes",
    "patch_from_env",
    "patch_module_attrs",
    "run_experiment",
    "run_split_repeated",
    "validate_experiment",
    "workspace_override_context",
]
