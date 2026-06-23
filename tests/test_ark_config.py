"""ARK coding-plan configuration regression tests."""

import importlib
from pathlib import Path

from dotenv import dotenv_values


def _reload_config(monkeypatch, **env):
    keys = [
        "PROVIDER",
        "ARK_API_KEY",
        "ARKCODE_API_KEY",
        "ARK_CODING_BASE_URL",
        "ARK_MODEL",
        "MINIMAX_API_KEY",
        "MINIMAX_BASE_URL",
        "MINIMAX_MODEL",
        "MAX_TOKENS",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    import agent.config as config

    return importlib.reload(config)


def test_default_minimax_provider_uses_ark_coding(monkeypatch):
    config = _reload_config(monkeypatch)

    assert config.ACTIVE_PROVIDER == "minimax"
    assert config.get_base_url() == "https://ark.cn-beijing.volces.com/api/coding"
    assert config.get_model() == "minimax-m3"
    assert config.MAX_TOKENS == 30000


def test_minimax_provider_ignores_legacy_minimax_endpoint_and_key(monkeypatch):
    config = _reload_config(
        monkeypatch,
        MINIMAX_API_KEY="legacy-minimax-key",
        MINIMAX_BASE_URL="https://api.minimax.chat",
        MINIMAX_MODEL="minimax2.7",
    )

    assert config.get_api_key() == ""
    assert config.get_base_url() == "https://ark.cn-beijing.volces.com/api/coding"
    assert config.get_model() == "minimax-m3"


def test_minimax_provider_supports_arkcode_api_key_alias(monkeypatch):
    config = _reload_config(monkeypatch, ARKCODE_API_KEY="arkcode-key")

    assert config.get_api_key() == "arkcode-key"


def test_env_example_loads_ark_coding_defaults():
    values = dotenv_values(Path(".env.example"))

    assert values["PROVIDER"] == "minimax"
    assert values["ARK_CODING_BASE_URL"] == "https://ark.cn-beijing.volces.com/api/coding"
    assert values["ARK_MODEL"] == "minimax-m3"
    assert values["MAX_TOKENS"] == "30000"
    assert "MINIMAX_BASE_URL" not in values
    assert "MINIMAX_API_KEY" not in values
    assert "MINIMAX_MODEL" not in values
