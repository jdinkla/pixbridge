"""Tests for pixbridge.providers.xai — XAIProvider with mocked SDK."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pixbridge.providers.xai import XAIProvider


@pytest.fixture
def provider() -> XAIProvider:
    return XAIProvider(api_key="test-key")


def _make_xai_response(url: str = "https://api.x.ai/image/abc.png"):
    """Build a mock xAI images.generate response."""
    data_item = SimpleNamespace(url=url)
    return SimpleNamespace(data=[data_item])


class TestXAICapabilities:
    def test_name(self, provider):
        assert provider.name == "xai"

    def test_default_model(self, provider):
        caps = provider.capabilities
        assert caps.default_model == "grok-imagine-image"

    def test_sizes_empty(self, provider):
        assert provider.capabilities.sizes == []

    def test_aspect_ratios(self, provider):
        caps = provider.capabilities
        assert set(caps.aspect_ratios) == {"20:9", "16:9", "4:3", "3:2", "1:1"}

    def test_no_quality_levels(self, provider):
        assert provider.capabilities.quality_levels is None

    def test_no_style_transfer(self, provider):
        assert provider.capabilities.supports_style_transfer is False

    def test_no_reference_images(self, provider):
        assert provider.capabilities.supports_reference_images is False


class TestXAIValidateParams:
    def test_valid_params(self, provider):
        provider.validate_params(model="grok-imagine-image", aspect_ratio="16:9")

    def test_rejects_3_4(self, provider):
        with pytest.raises(ValueError, match="not supported by xAI"):
            provider.validate_params(aspect_ratio="3:4")

    def test_rejects_9_16(self, provider):
        with pytest.raises(ValueError, match="not supported by xAI"):
            provider.validate_params(aspect_ratio="9:16")

    def test_quality_not_supported(self, provider):
        with pytest.raises(ValueError, match="does not support quality"):
            provider.validate_params(quality="high")

    def test_none_params_accepted(self, provider):
        provider.validate_params()


class TestXAIGenerate:
    @patch("pixbridge.providers.xai.requests.get")
    def test_basic_generation(self, mock_get, provider, sample_prompt, tiny_png_bytes):
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_xai_response()
        provider._client = mock_client

        mock_response = MagicMock()
        mock_response.content = tiny_png_bytes
        mock_response.headers = {"content-type": "image/png"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = provider.generate(sample_prompt)

        assert result.image_data == tiny_png_bytes
        assert result.mime_type == "image/png"
        assert result.provider == "xai"
        assert result.model == "grok-imagine-image"

    @patch("pixbridge.providers.xai.requests.get")
    def test_passes_extra_body_aspect_ratio(self, mock_get, provider, sample_prompt, tiny_png_bytes):
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_xai_response()
        provider._client = mock_client

        mock_response = MagicMock()
        mock_response.content = tiny_png_bytes
        mock_response.headers = {"content-type": "image/png"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider.generate(sample_prompt, aspect_ratio="4:3")

        call_kwargs = mock_client.images.generate.call_args[1]
        assert call_kwargs["extra_body"] == {"aspect_ratio": "4:3"}

    @patch("pixbridge.providers.xai.requests.get")
    def test_downloads_from_url(self, mock_get, provider, sample_prompt, tiny_png_bytes):
        image_url = "https://api.x.ai/image/abc.png"
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_xai_response(url=image_url)
        provider._client = mock_client

        mock_response = MagicMock()
        mock_response.content = tiny_png_bytes
        mock_response.headers = {"content-type": "image/png"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = provider.generate(sample_prompt)

        mock_get.assert_called_once_with(image_url, timeout=60)
        assert result.metadata["image_url"] == image_url

    @patch("pixbridge.providers.xai.requests.get")
    def test_strips_charset_from_content_type(self, mock_get, provider, sample_prompt, tiny_png_bytes):
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_xai_response()
        provider._client = mock_client

        mock_response = MagicMock()
        mock_response.content = tiny_png_bytes
        mock_response.headers = {"content-type": "image/jpeg; charset=utf-8"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = provider.generate(sample_prompt)

        assert result.mime_type == "image/jpeg"

    @patch("pixbridge.providers.xai.requests.get")
    def test_defaults_mime_to_png(self, mock_get, provider, sample_prompt, tiny_png_bytes):
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_xai_response()
        provider._client = mock_client

        mock_response = MagicMock()
        mock_response.content = tiny_png_bytes
        mock_response.headers = {}  # no content-type
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = provider.generate(sample_prompt)

        assert result.mime_type == "image/png"

    def test_unsupported_aspect_ratio_raises(self, provider, sample_prompt):
        with pytest.raises(ValueError, match="not supported by xAI"):
            provider.generate(sample_prompt, aspect_ratio="3:4")

    @patch("pixbridge.providers.xai.requests.get")
    def test_applies_defaults(self, mock_get, provider, sample_prompt, tiny_png_bytes):
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_xai_response()
        provider._client = mock_client

        mock_response = MagicMock()
        mock_response.content = tiny_png_bytes
        mock_response.headers = {"content-type": "image/png"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = provider.generate(sample_prompt)

        assert result.metadata["aspect_ratio"] == "16:9"


class TestXAIGetClient:
    def test_lazy_init(self, provider):
        assert provider._client is None

    @patch("pixbridge.providers.xai.OpenAI")
    def test_creates_client_with_custom_base_url(self, mock_cls, provider):
        mock_cls.return_value = MagicMock()
        client = provider._get_client()
        mock_cls.assert_called_once_with(
            api_key="test-key", base_url="https://api.x.ai/v1",
        )
        assert client is not None

    @patch("pixbridge.providers.xai.OpenAI")
    def test_caches_client(self, mock_cls, provider):
        mock_cls.return_value = MagicMock()
        c1 = provider._get_client()
        c2 = provider._get_client()
        assert c1 is c2
        mock_cls.assert_called_once()
