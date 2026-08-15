from types import SimpleNamespace

from better_harness.agent import (
    build_proposer_model,
    proposer_recursion_limit,
    summarize_outer_usage,
)


def test_proposer_model_splits_explicit_provider_route(monkeypatch):
    captured = {}

    def init_chat_model(model, **kwargs):
        captured.update(model=model, **kwargs)
        return "client"

    monkeypatch.setattr(
        "better_harness.agent.importlib.import_module",
        lambda _name: SimpleNamespace(init_chat_model=init_chat_model),
    )

    assert build_proposer_model("openai/deepseek-v4-flash") == "client"
    assert captured == {
        "model": "deepseek-v4-flash",
        "model_provider": "openai",
        "timeout": 120,
        "max_retries": 2,
    }


def test_proposer_model_keeps_inferable_model_name(monkeypatch):
    captured = {}

    def init_chat_model(model, **kwargs):
        captured.update(model=model, **kwargs)
        return "client"

    monkeypatch.setattr(
        "better_harness.agent.importlib.import_module",
        lambda _name: SimpleNamespace(init_chat_model=init_chat_model),
    )

    build_proposer_model("claude-sonnet-4-6")
    assert captured["model"] == "claude-sonnet-4-6"
    assert "model_provider" not in captured


def test_proposer_turn_budget_allows_multiple_graph_nodes_per_turn():
    assert proposer_recursion_limit(60) == 240


def test_outer_usage_sums_model_messages_only():
    result = {
        "messages": [
            {"type": "human"},
            {
                "type": "ai",
                "usage_metadata": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
            },
            {"type": "tool"},
            {
                "type": "ai",
                "usage_metadata": {"input_tokens": 20, "output_tokens": 3, "total_tokens": 23},
            },
        ]
    }
    assert summarize_outer_usage(result) == {
        "model_calls": 2,
        "input_tokens": 30,
        "output_tokens": 5,
        "total_tokens": 35,
    }
