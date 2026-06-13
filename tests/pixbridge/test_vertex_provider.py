"""Tests for pixbridge.providers.vertex — ADC-based init logic and client caching."""

from unittest.mock import MagicMock, patch

import pytest

from pixbridge.providers.vertex import VertexProvider


class TestInit:
    def test_requires_project_env(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        with pytest.raises(OSError, match="GOOGLE_CLOUD_PROJECT"):
            VertexProvider()

    def test_defaults_location_to_global(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj-123")
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        provider = VertexProvider()
        assert provider._project == "proj-123"
        assert provider._location == "global"
        # No API key required; client is lazily constructed.
        assert provider._client is None

    def test_honours_explicit_location(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj-123")
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        provider = VertexProvider()
        assert provider._location == "us-central1"

    def test_no_api_key_env_keys(self):
        assert VertexProvider.ENV_KEYS == []


class TestName:
    def test_name(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj-123")
        assert VertexProvider().name == "vertex"


class TestGetClient:
    def test_constructs_vertex_client_with_project_and_location(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj-123")
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west4")
        provider = VertexProvider()

        with patch("pixbridge.providers.vertex.genai.Client") as mock_client:
            instance = MagicMock()
            mock_client.return_value = instance

            client = provider._get_client()

            mock_client.assert_called_once_with(
                vertexai=True,
                project="proj-123",
                location="europe-west4",
            )
            assert client is instance

    def test_client_is_cached(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj-123")
        provider = VertexProvider()

        with patch("pixbridge.providers.vertex.genai.Client") as mock_client:
            mock_client.return_value = MagicMock()
            first = provider._get_client()
            second = provider._get_client()

            assert first is second
            mock_client.assert_called_once()
