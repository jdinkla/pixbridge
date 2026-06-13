"""Tests for pixbridge.providers.gemini — GeminiProvider with mocked SDK."""

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from pixbridge.providers.gemini import GeminiProvider


@pytest.fixture
def provider() -> GeminiProvider:
    return GeminiProvider(api_key="test-key")


def _make_gemini_response(image_data: bytes, mime_type: str = "image/png"):
    """Build a mock Gemini response with inline_data."""
    part = SimpleNamespace(
        inline_data=SimpleNamespace(data=image_data, mime_type=mime_type),
    )
    candidate = SimpleNamespace(content=SimpleNamespace(parts=[part]))
    return SimpleNamespace(candidates=[candidate])


def _make_text_only_response():
    """Build a mock Gemini response with only text (no image)."""
    part = SimpleNamespace(inline_data=None, text="Some text response")
    candidate = SimpleNamespace(content=SimpleNamespace(parts=[part]))
    return SimpleNamespace(candidates=[candidate])


class TestGeminiCapabilities:
    def test_name(self, provider):
        assert provider.name == "gemini"

    def test_default_model(self, provider):
        caps = provider.capabilities
        assert caps.default_model == "gemini-3-pro-image-preview"

    def test_sizes(self, provider):
        caps = provider.capabilities
        assert "1K" in caps.sizes
        assert "2K" in caps.sizes

    def test_aspect_ratios(self, provider):
        caps = provider.capabilities
        assert set(caps.aspect_ratios) == {"16:9", "4:3", "3:4", "9:16", "1:1"}

    def test_no_quality_levels(self, provider):
        assert provider.capabilities.quality_levels is None

    def test_supports_style_transfer(self, provider):
        assert provider.capabilities.supports_style_transfer is True

    def test_supports_reference_images(self, provider):
        assert provider.capabilities.supports_reference_images is True


class TestGeminiGenerate:
    def test_basic_generation(self, provider, sample_prompt, tiny_png_bytes):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_gemini_response(
            tiny_png_bytes
        )
        provider._client = mock_client

        result = provider.generate(sample_prompt)

        assert result.image_data == tiny_png_bytes
        assert result.mime_type == "image/png"
        assert result.provider == "gemini"
        assert result.model == "gemini-3-pro-image-preview"
        mock_client.models.generate_content.assert_called_once()

    def test_applies_defaults(self, provider, sample_prompt, tiny_png_bytes):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_gemini_response(
            tiny_png_bytes
        )
        provider._client = mock_client

        result = provider.generate(sample_prompt)

        assert result.metadata["size"] == "1K"
        assert result.metadata["aspect_ratio"] == "16:9"

    def test_custom_params(self, provider, sample_prompt, tiny_png_bytes):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_gemini_response(
            tiny_png_bytes
        )
        provider._client = mock_client

        result = provider.generate(
            sample_prompt, size="2K", aspect_ratio="4:3",
        )

        assert result.metadata["size"] == "2K"
        assert result.metadata["aspect_ratio"] == "4:3"

    def test_base64_string_decoded(self, provider, sample_prompt, tiny_png_bytes):
        """When Gemini returns base64-encoded string instead of bytes."""
        encoded = base64.b64encode(tiny_png_bytes).decode("ascii")
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_gemini_response(
            encoded
        )
        provider._client = mock_client

        result = provider.generate(sample_prompt)

        assert result.image_data == tiny_png_bytes

    def test_no_image_in_response_raises(self, provider, sample_prompt):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_text_only_response()
        provider._client = mock_client

        with pytest.raises(ValueError, match="No image found"):
            provider.generate(sample_prompt)

    def test_invalid_size_raises(self, provider, sample_prompt):
        with pytest.raises(ValueError, match="Invalid size"):
            provider.generate(sample_prompt, size="4K")


class TestGeminiGenerateWithReferences:
    def test_with_reference_images(self, provider, sample_prompt, tiny_png_bytes, tmp_path):
        # Create reference images on disk
        ref1 = tmp_path / "ref1.png"
        ref2 = tmp_path / "ref2.png"
        Image.new("RGB", (10, 10), "blue").save(ref1)
        Image.new("RGB", (10, 10), "green").save(ref2)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_gemini_response(
            tiny_png_bytes
        )
        provider._client = mock_client

        result = provider.generate_with_references(
            sample_prompt, reference_images=[ref1, ref2],
        )

        assert result.provider == "gemini"
        assert result.metadata["reference_images"] == [str(ref1), str(ref2)]
        assert result.metadata["temperature"] == 0.1

        # Verify multimodal contents were passed
        call_kwargs = mock_client.models.generate_content.call_args[1]
        contents = call_kwargs["contents"]
        # 2 PIL images + 1 text prompt
        assert len(contents) == 3

    def test_custom_temperature(self, provider, sample_prompt, tiny_png_bytes, tmp_path):
        ref = tmp_path / "ref.png"
        Image.new("RGB", (10, 10)).save(ref)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_gemini_response(
            tiny_png_bytes
        )
        provider._client = mock_client

        result = provider.generate_with_references(
            sample_prompt, reference_images=[ref], temperature=0.5,
        )

        assert result.metadata["temperature"] == 0.5

    def test_caps_at_six_references(self, provider, sample_prompt, tiny_png_bytes, tmp_path):
        refs = []
        for i in range(8):
            ref = tmp_path / f"ref{i}.png"
            Image.new("RGB", (10, 10)).save(ref)
            refs.append(ref)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_gemini_response(
            tiny_png_bytes
        )
        provider._client = mock_client

        result = provider.generate_with_references(
            sample_prompt, reference_images=refs,
        )

        # Only first 6 should be in metadata
        assert len(result.metadata["reference_images"]) == 6

    def test_skips_nonexistent_references(self, provider, sample_prompt, tiny_png_bytes, tmp_path):
        existing = tmp_path / "exists.png"
        Image.new("RGB", (10, 10)).save(existing)
        nonexistent = tmp_path / "missing.png"

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_gemini_response(
            tiny_png_bytes
        )
        provider._client = mock_client

        provider.generate_with_references(
            sample_prompt, reference_images=[existing, nonexistent],
        )

        # Should still succeed — nonexistent is skipped in PIL loading
        call_kwargs = mock_client.models.generate_content.call_args[1]
        contents = call_kwargs["contents"]
        # 1 PIL image + 1 text prompt (nonexistent skipped)
        assert len(contents) == 2

    def test_no_image_in_response_raises(self, provider, sample_prompt, tmp_path):
        ref = tmp_path / "ref.png"
        Image.new("RGB", (10, 10)).save(ref)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_text_only_response()
        provider._client = mock_client

        with pytest.raises(ValueError, match="No image found"):
            provider.generate_with_references(
                sample_prompt, reference_images=[ref],
            )


class TestGeminiStyleTransfer:
    def test_basic_style_transfer(self, provider, tiny_png_bytes, tmp_path):
        input_image = tmp_path / "input.png"
        Image.new("RGB", (10, 10)).save(input_image)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_gemini_response(
            tiny_png_bytes
        )
        provider._client = mock_client

        result = provider.style_transfer(input_image, "watercolor style")

        assert result.provider == "gemini"
        assert result.metadata["style_transfer"] is True
        assert result.metadata["input_image"] == str(input_image)
        mock_client.models.generate_content.assert_called_once()

    def test_uses_style_transfer_model(self, provider, tiny_png_bytes, tmp_path):
        input_image = tmp_path / "input.png"
        Image.new("RGB", (10, 10)).save(input_image)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_gemini_response(
            tiny_png_bytes
        )
        provider._client = mock_client

        result = provider.style_transfer(input_image, "style")

        assert result.model == "gemini-3-pro-image-preview"

    def test_no_image_in_response_raises(self, provider, tmp_path):
        input_image = tmp_path / "input.png"
        Image.new("RGB", (10, 10)).save(input_image)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_text_only_response()
        provider._client = mock_client

        with pytest.raises(ValueError, match="No image found"):
            provider.style_transfer(input_image, "style")


class TestGeminiGetClient:
    def test_lazy_init(self, provider):
        assert provider._client is None

    @patch("pixbridge.providers.gemini.genai.Client")
    def test_creates_client_with_api_key(self, mock_cls, provider):
        mock_cls.return_value = MagicMock()
        client = provider._get_client()
        mock_cls.assert_called_once_with(api_key="test-key")
        assert client is not None

    @patch("pixbridge.providers.gemini.genai.Client")
    def test_caches_client(self, mock_cls, provider):
        mock_cls.return_value = MagicMock()
        c1 = provider._get_client()
        c2 = provider._get_client()
        assert c1 is c2
        mock_cls.assert_called_once()
