from types import SimpleNamespace

from benchmarks.fabv2.workspace.accounting import merge_tool_usage, result_tokens


def test_result_tokens_includes_main_metadata_and_compaction():
    result = SimpleNamespace(
        final_aggregated_metadata={"total_input_tokens": 100, "total_output_tokens": 20},
        final_compaction_metadata={"total_input_tokens": 30, "total_output_tokens": 5},
    )

    assert result_tokens(result) == 155


def test_merge_tool_usage_accounts_for_recovery_submission():
    main = SimpleNamespace(tool_usage={"edgar_search": 4, "calculator": 2})
    recovery = SimpleNamespace(tool_usage={"submit_final_result": 1, "calculator": 1})

    assert merge_tool_usage(main, recovery) == {
        "edgar_search": 4,
        "calculator": 3,
        "submit_final_result": 1,
    }
