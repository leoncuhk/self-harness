from types import SimpleNamespace

from better_harness.agent import build_proposer_model


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
