from types import SimpleNamespace

from better_harness.usage import total_tokens


def test_total_tokens_accepts_combined_provider_metadata():
    assert total_tokens({"total_tokens": 123}) == 123


def test_total_tokens_sums_input_and_output_aggregates_without_double_counting():
    metadata = SimpleNamespace(
        total_input_tokens=59_288,
        total_output_tokens=4_132,
        cache_read_tokens=54_912,
        reasoning_tokens=1_949,
    )
    assert total_tokens(metadata) == 63_420


def test_total_tokens_preserves_unmeasured_state():
    assert total_tokens(None) is None
    assert total_tokens({"cost": 1.0}) is None
