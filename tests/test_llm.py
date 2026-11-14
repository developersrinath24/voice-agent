"""Provider ordering and failover configuration."""

import pytest

from app.core.config import settings
from app.services.llm import LLMNotConfigured, build_llm, configured_providers


@pytest.fixture(autouse=True)
def _both_keys(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-deepseek")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini")


def test_order_follows_llm_order(monkeypatch):
    monkeypatch.setattr(settings, "LLM_ORDER", "gemini,deepseek")
    assert configured_providers() == ["gemini", "deepseek"]

    monkeypatch.setattr(settings, "LLM_ORDER", "deepseek,gemini")
    assert configured_providers() == ["deepseek", "gemini"]


def test_provider_without_a_key_is_skipped(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_ORDER", "deepseek,gemini")
    assert configured_providers() == ["gemini"]


def test_provider_missing_from_order_is_appended(monkeypatch):
    """A configured key must never be silently ignored."""
    monkeypatch.setattr(settings, "LLM_ORDER", "gemini")
    assert configured_providers() == ["gemini", "deepseek"]


def test_unknown_names_and_whitespace_are_ignored(monkeypatch):
    monkeypatch.setattr(settings, "LLM_ORDER", " gemini , nonsense , deepseek ")
    assert configured_providers() == ["gemini", "deepseek"]


def test_no_keys_raises_clearly(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    with pytest.raises(LLMNotConfigured, match="No language model configured"):
        build_llm()


def test_single_provider_is_not_wrapped_in_fallbacks(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    llm = build_llm()
    assert type(llm).__name__ != "RunnableWithFallbacks"


def test_two_providers_are_wrapped_in_fallbacks(monkeypatch):
    llm = build_llm()
    assert type(llm).__name__ == "RunnableWithFallbacks"
