from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from self_harness.core import load_experiment
from self_harness.diagnostics import (
    DEFAULT_DIAGNOSTICS,
    DiagnosticContract,
    DiagnosticEvidence,
    FacetRule,
    collect_diagnostic_facets,
    load_diagnostic_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def test_fab_profile_is_domain_owned_and_loaded_by_contract():
    experiment = load_experiment(ROOT / "configs" / "fabv2.toml")

    assert experiment.diagnostics.name == "fabv2-finance-v1"
    assert "finance_semantics_computation" in experiment.diagnostics.layers
    assert {facet.name for facet in experiment.diagnostics.facets} == {
        "answer_materialization",
        "cash_flow_reconciliation",
        "filing_attachment_resolution",
        "forecast_period_provenance",
    }
    changed = replace(
        experiment,
        diagnostics=replace(experiment.diagnostics, guidance="different frozen guidance"),
    )
    assert changed.evaluation_fingerprint != experiment.evaluation_fingerprint


def test_generic_contract_does_not_inherit_finance_vocabulary():
    text = "Actual source period and guidance forecast require FCFF SBC CapEx reconciliation."

    facets = collect_diagnostic_facets(
        DEFAULT_DIAGNOSTICS,
        DiagnosticEvidence(research_tail=text),
    )

    assert facets == ()
    assert "finance" not in DEFAULT_DIAGNOSTICS.render().lower()


def test_declarative_rule_supports_conjunctive_routing():
    contract = DiagnosticContract(
        name="science",
        layers=("apparatus", "experiment_design", "analysis"),
        facets=(
            FacetRule(
                name="unit_consistency",
                patterns=(r"\bkelvin\b", r"\bcelsius\b"),
                minimum_matches=2,
            ),
        ),
    )

    only_one = collect_diagnostic_facets(
        contract,
        DiagnosticEvidence(research_tail="temperature in Kelvin"),
    )
    both = collect_diagnostic_facets(
        contract,
        DiagnosticEvidence(research_tail="mixed Kelvin and Celsius values"),
    )

    assert only_one == ()
    assert both == ("unit_consistency",)


def test_profile_file_cannot_silently_override_inline_contract(tmp_path: Path):
    profile = tmp_path / "profile.toml"
    profile.write_text('name = "x"\nlayers = ["one"]\n')

    with pytest.raises(ValueError, match="cannot be combined"):
        load_diagnostic_contract(
            {"profile_file": str(profile), "name": "different"},
            config_dir=tmp_path,
        )
