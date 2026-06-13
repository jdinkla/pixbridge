"""Tests for pixbridge.providers — get_provider, list_providers."""

import pytest

from pixbridge.providers import get_provider, list_providers
from pixbridge.providers.gemini import GeminiProvider
from pixbridge.providers.openai import OpenAIProvider
from pixbridge.providers.xai import XAIProvider


class TestListProviders:
    def test_returns_known_providers(self):
        providers = list_providers()
        assert "gemini" in providers
        assert "openai" in providers
        assert "xai" in providers
        assert "vertex" in providers

    def test_returns_list(self):
        assert isinstance(list_providers(), list)

    def test_is_sorted(self):
        result = list_providers()
        assert result == sorted(result)


class TestGetProvider:
    def test_get_gemini(self):
        p = get_provider("gemini", api_key="fake-key")
        assert isinstance(p, GeminiProvider)

    def test_get_openai(self):
        p = get_provider("openai", api_key="fake-key")
        assert isinstance(p, OpenAIProvider)

    def test_get_xai(self):
        p = get_provider("xai", api_key="fake-key")
        assert isinstance(p, XAIProvider)

    def test_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("azure")

    def test_api_key_passed_through(self):
        p = get_provider("gemini", api_key="test-key-123")
        assert p._api_key == "test-key-123"

    def test_none_api_key(self):
        p = get_provider("gemini")
        assert p._api_key is None

    def test_get_vertex_lazy_loads(self, monkeypatch):
        # vertex is an opt-in provider, registered on demand via _ensure_provider.
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj-123")
        from pixbridge.providers.vertex import VertexProvider

        p = get_provider("vertex")
        assert isinstance(p, VertexProvider)
