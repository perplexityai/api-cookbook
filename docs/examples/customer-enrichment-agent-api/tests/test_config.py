from __future__ import annotations

import pytest

from customer_enrichment.config import ConfigurationError, Settings


def test_default_model_is_glm_5_3(monkeypatch) -> None:
    monkeypatch.delenv("MODEL", raising=False)
    assert Settings.load().model == "perplexity/glm-5.3"


def test_live_command_requires_key_and_explicit_spend_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("PERPLEXITY_API_KEY", "")
    monkeypatch.setenv("CONFIRM_LIVE_SPEND", "NO")
    settings = Settings.load()
    with pytest.raises(ConfigurationError) as caught:
        settings.require_live()
    message = str(caught.value)
    assert "PERPLEXITY_API_KEY" in message
    assert "CONFIRM_LIVE_SPEND" in message


def test_model_environment_override(monkeypatch) -> None:
    monkeypatch.setenv("MODEL", "openai/gpt-5.6-terra")
    assert Settings.load().model == "openai/gpt-5.6-terra"
