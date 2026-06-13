"""Tests for pixbridge.client — ImageClient with mocked provider."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from pixbridge.client import VALID_ASPECT_RATIOS, VALID_SIZES, GeminiImageClient, ImageClient
from pixbridge.providers.base import GenerationResult, ProviderCapabilities


def _make_provider(
    supports_style_transfer: bool = False,
    supports_reference_images: bool = False,
) -> MagicMock:
    """Create a mock provider with configurable capabilities."""
    provider = MagicMock()
    provider.name = "mock"
    provider.capabilities = ProviderCapabilities(
        sizes=["1K", "2K"],
        aspect_ratios=["16:9", "4:3", "1:1"],
        default_model="default-model",
        default_size="1K",
        default_aspect_ratio="16:9",
        supports_style_transfer=supports_style_transfer,
        supports_reference_images=supports_reference_images,
    )
    return provider


def _make_result(tiny_png_bytes: bytes) -> GenerationResult:
    return GenerationResult(
        image_data=tiny_png_bytes,
        mime_type="image/png",
        provider="mock",
        model="default-model",
        metadata={"size": "1K", "aspect_ratio": "16:9"},
    )


class TestImageClientInit:
    def test_defaults(self):
        client = ImageClient()
        assert client.provider_name == "gemini"
        assert client._provider is None
        assert client.usage_log is None

    def test_custom_provider(self):
        client = ImageClient(provider="openai", api_key="key")
        assert client.provider_name == "openai"
        assert client._api_key == "key"

    def test_lazy_provider(self):
        client = ImageClient()
        assert client._provider is None

    def test_api_key_property(self):
        client = ImageClient(api_key="my-key")
        assert client.api_key == "my-key"

    def test_usage_log(self, tmp_path):
        log = tmp_path / "usage.jsonl"
        client = ImageClient(usage_log=log)
        assert client.usage_log == log


class TestImageClientProvider:
    @patch("pixbridge.client.get_provider")
    def test_lazy_initializes_provider(self, mock_get):
        mock_provider = MagicMock()
        mock_get.return_value = mock_provider

        client = ImageClient(provider="openai", api_key="key")
        p = client.provider

        mock_get.assert_called_once_with("openai", "key")
        assert p is mock_provider

    @patch("pixbridge.client.get_provider")
    def test_caches_provider(self, mock_get):
        mock_get.return_value = MagicMock()
        client = ImageClient()

        p1 = client.provider
        p2 = client.provider

        assert p1 is p2
        mock_get.assert_called_once()


class TestGenerateImage:
    def test_generates_and_saves(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient()
        mock_provider = _make_provider()
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        output_dir = tmp_path / "output"
        path = client.generate_image(sample_prompt, output_dir)

        assert path.exists()
        assert path.parent == output_dir
        assert path.suffix == ".png"
        mock_provider.generate.assert_called_once()

    def test_creates_output_dir(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient()
        mock_provider = _make_provider()
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        output_dir = tmp_path / "deep" / "nested"
        path = client.generate_image(sample_prompt, output_dir)

        assert output_dir.exists()
        assert path.exists()

    def test_passes_params_to_provider(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient()
        mock_provider = _make_provider()
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        client.generate_image(
            sample_prompt, tmp_path,
            model="m", size="2K", aspect_ratio="4:3", quality="high",
        )

        call_kwargs = mock_provider.generate.call_args[1]
        assert call_kwargs["model"] == "m"
        assert call_kwargs["size"] == "2K"
        assert call_kwargs["aspect_ratio"] == "4:3"
        assert call_kwargs["quality"] == "high"

    def test_string_output_dir(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient()
        mock_provider = _make_provider()
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        path = client.generate_image(sample_prompt, str(tmp_path / "out"))

        assert path.exists()


class TestGenerateImageSizeResolution:
    def test_preset_resolved_for_gemini(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient(provider="gemini")
        mock_provider = _make_provider()
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        client.generate_image(sample_prompt, tmp_path, size="1080p")

        call_kwargs = mock_provider.generate.call_args[1]
        assert call_kwargs["size"] == "1K"
        assert call_kwargs["aspect_ratio"] == "16:9"

    def test_wxh_resolved_for_gemini(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient(provider="gemini")
        mock_provider = _make_provider()
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        client.generate_image(sample_prompt, tmp_path, size="1920x1080")

        call_kwargs = mock_provider.generate.call_args[1]
        assert call_kwargs["size"] == "2K"
        assert call_kwargs["aspect_ratio"] == "16:9"

    def test_wxh_resolved_for_openai(self, sample_prompt, tiny_png_bytes, tmp_path):
        # OpenAI now passes valid WxH through unchanged — no silent rewrite.
        client = ImageClient(provider="openai")
        mock_provider = _make_provider()
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        client.generate_image(sample_prompt, tmp_path, size="2048x1152")

        call_kwargs = mock_provider.generate.call_args[1]
        assert call_kwargs["size"] == "2048x1152"
        assert call_kwargs["aspect_ratio"] == "16:9"

    def test_invalid_wxh_for_openai_raises(self, sample_prompt, tiny_png_bytes, tmp_path):
        # `1920x1080` is not valid for OpenAI (1080 not divisible by 16). The
        # silent-snap fallback that used to mask this is gone.
        client = ImageClient(provider="openai")
        mock_provider = _make_provider()
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        with pytest.raises(ValueError, match="divisible by 16"):
            client.generate_image(sample_prompt, tmp_path, size="1920x1080")

    def test_explicit_aspect_ratio_not_overridden(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient(provider="gemini")
        mock_provider = _make_provider()
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        client.generate_image(sample_prompt, tmp_path, size="1920x1080", aspect_ratio="4:3")

        call_kwargs = mock_provider.generate.call_args[1]
        assert call_kwargs["size"] == "2K"
        assert call_kwargs["aspect_ratio"] == "4:3"

    def test_valid_provider_size_passes_through(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient(provider="gemini")
        mock_provider = _make_provider()
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        client.generate_image(sample_prompt, tmp_path, size="2K")

        call_kwargs = mock_provider.generate.call_args[1]
        assert call_kwargs["size"] == "2K"
        assert call_kwargs["aspect_ratio"] is None

    def test_none_size_skips_resolution(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient(provider="gemini")
        mock_provider = _make_provider()
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        client.generate_image(sample_prompt, tmp_path, size=None)

        call_kwargs = mock_provider.generate.call_args[1]
        assert call_kwargs["size"] is None


class TestGenerateWithReferencesSizeResolution:
    def test_preset_resolved(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient(provider="gemini")
        mock_provider = _make_provider(supports_reference_images=True)
        mock_provider.generate_with_references.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        refs = [tmp_path / "ref.png"]
        client.generate_image_with_references(
            sample_prompt, refs, tmp_path / "output", size="2160p",
        )

        call_kwargs = mock_provider.generate_with_references.call_args[1]
        assert call_kwargs["size"] == "2K"
        assert call_kwargs["aspect_ratio"] == "16:9"

    def test_wxh_resolved(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient(provider="gemini")
        mock_provider = _make_provider(supports_reference_images=True)
        mock_provider.generate_with_references.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        refs = [tmp_path / "ref.png"]
        client.generate_image_with_references(
            sample_prompt, refs, tmp_path / "output", size="1920x1080",
        )

        call_kwargs = mock_provider.generate_with_references.call_args[1]
        assert call_kwargs["size"] == "2K"
        assert call_kwargs["aspect_ratio"] == "16:9"

    def test_empty_refs_fallback_also_resolves(self, sample_prompt, tiny_png_bytes, tmp_path):
        """With no reference images, the text-only path still resolves size presets."""
        client = ImageClient(provider="gemini")
        mock_provider = _make_provider(supports_reference_images=True)
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        client.generate_image_with_references(
            sample_prompt, [], tmp_path / "output", size="1080p",
        )

        call_kwargs = mock_provider.generate.call_args[1]
        assert call_kwargs["size"] == "1K"
        assert call_kwargs["aspect_ratio"] == "16:9"


class TestGenerateImageWithReferences:
    def test_uses_references_when_supported(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient()
        mock_provider = _make_provider(supports_reference_images=True)
        mock_provider.generate_with_references.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        refs = [tmp_path / "ref1.png"]
        path = client.generate_image_with_references(
            sample_prompt, refs, tmp_path / "output",
        )

        assert path.exists()
        mock_provider.generate_with_references.assert_called_once()
        mock_provider.generate.assert_not_called()

    def test_raises_when_provider_unsupported(self, sample_prompt, tiny_png_bytes, tmp_path):
        """Providers without reference-image support now raise rather than silently drop them."""
        client = ImageClient()
        mock_provider = _make_provider(supports_reference_images=False)
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        refs = [tmp_path / "ref1.png"]
        with pytest.raises(ValueError, match="does not support reference"):
            client.generate_image_with_references(
                sample_prompt, refs, tmp_path / "output",
            )
        mock_provider.generate.assert_not_called()
        mock_provider.generate_with_references.assert_not_called()

    def test_empty_refs_uses_text_only(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient()
        mock_provider = _make_provider(supports_reference_images=True)
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        client.generate_image_with_references(
            sample_prompt, [], tmp_path / "output",
        )

        mock_provider.generate.assert_called_once()

    def test_passes_temperature(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient()
        mock_provider = _make_provider(supports_reference_images=True)
        mock_provider.generate_with_references.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        refs = [tmp_path / "ref.png"]
        client.generate_image_with_references(
            sample_prompt, refs, tmp_path / "output", temperature=0.3,
        )

        call_kwargs = mock_provider.generate_with_references.call_args[1]
        assert call_kwargs["temperature"] == 0.3


class TestStyleTransferImage:
    def test_basic_style_transfer(self, tiny_png_bytes, tmp_path):
        client = ImageClient()
        mock_provider = _make_provider(supports_style_transfer=True)
        mock_provider.style_transfer.return_value = GenerationResult(
            image_data=tiny_png_bytes,
            mime_type="image/png",
            provider="mock",
            model="m",
            metadata={"style_transfer": True},
        )
        client._provider = mock_provider

        input_img = tmp_path / "input.png"
        Image.new("RGB", (10, 10)).save(input_img)
        output_img = tmp_path / "output.png"

        path = client.style_transfer_image(input_img, "raw style text", output_img)

        assert path == output_img
        assert output_img.exists()
        mock_provider.style_transfer.assert_called_once()

    def test_overwrites_in_place_when_no_output(self, tiny_png_bytes, tmp_path):
        client = ImageClient()
        mock_provider = _make_provider(supports_style_transfer=True)
        mock_provider.style_transfer.return_value = GenerationResult(
            image_data=tiny_png_bytes,
            mime_type="image/png",
            provider="mock",
            model="m",
        )
        client._provider = mock_provider

        input_img = tmp_path / "input.png"
        Image.new("RGB", (10, 10)).save(input_img)

        path = client.style_transfer_image(input_img, "style text")

        assert path == input_img

    def test_unsupported_provider_raises(self, tmp_path):
        client = ImageClient()
        mock_provider = _make_provider(supports_style_transfer=False)
        client._provider = mock_provider

        input_img = tmp_path / "input.png"
        Image.new("RGB", (10, 10)).save(input_img)

        with pytest.raises(ValueError, match="does not support style transfer"):
            client.style_transfer_image(input_img, "style")

    def test_missing_input_raises(self, tmp_path):
        client = ImageClient()
        mock_provider = _make_provider(supports_style_transfer=True)
        client._provider = mock_provider

        with pytest.raises(FileNotFoundError, match="Input image not found"):
            client.style_transfer_image(tmp_path / "nope.png", "style")

    def test_string_paths(self, tiny_png_bytes, tmp_path):
        client = ImageClient()
        mock_provider = _make_provider(supports_style_transfer=True)
        mock_provider.style_transfer.return_value = GenerationResult(
            image_data=tiny_png_bytes,
            mime_type="image/png",
            provider="mock",
            model="m",
        )
        client._provider = mock_provider

        input_img = tmp_path / "input.png"
        Image.new("RGB", (10, 10)).save(input_img)
        output_img = tmp_path / "output.png"

        path = client.style_transfer_image(str(input_img), "style", str(output_img))

        assert Path(path).exists()


class TestResolveStyle:
    def test_file_path(self, tmp_path):
        style_file = tmp_path / "my-style.md"
        style_file.write_text("Custom style description")

        result = ImageClient._resolve_style(str(style_file))

        assert result == "Custom style description"

    def test_preset_name_with_subdir_prefix(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        preset_dir = tmp_path / "prompts" / "style-transfer" / "anime"
        preset_dir.mkdir(parents=True)
        (preset_dir / "anime-dark.md").write_text("Anime dark style")

        result = ImageClient._resolve_style("anime/anime-dark")

        assert result == "Anime dark style"

    def test_bare_name_searches_subdirs(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        preset_dir = tmp_path / "prompts" / "style-transfer" / "anime"
        preset_dir.mkdir(parents=True)
        (preset_dir / "anime-dark.md").write_text("Anime dark style")

        result = ImageClient._resolve_style("anime-dark")

        assert result == "Anime dark style"

    def test_raw_text_fallback(self):
        result = ImageClient._resolve_style("watercolor painting with bold strokes")
        assert result == "watercolor painting with bold strokes"


class TestListStylePresets:
    def test_lists_presets_with_subdir_prefix(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        preset_dir = tmp_path / "prompts" / "style-transfer"
        (preset_dir / "anime").mkdir(parents=True)
        (preset_dir / "noir").mkdir(parents=True)
        (preset_dir / "anime" / "anime-dark.md").write_text("...")
        (preset_dir / "noir" / "vintage-editorial-noir.md").write_text("...")

        presets = ImageClient.list_style_presets()

        assert presets == ["anime/anime-dark", "noir/vintage-editorial-noir"]

    def test_empty_when_no_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert ImageClient.list_style_presets() == []


class TestAvailableProviders:
    def test_returns_provider_names(self):
        providers = ImageClient.available_providers()
        assert "gemini" in providers
        assert "openai" in providers
        assert "xai" in providers


class TestBackwardCompatibility:
    def test_gemini_image_client(self):
        client = GeminiImageClient(api_key="key")
        assert isinstance(client, ImageClient)
        assert client.provider_name == "gemini"
        assert client._api_key == "key"

    def test_valid_sizes_constant(self):
        assert VALID_SIZES == ["1K", "2K"]

    def test_valid_aspect_ratios_constant(self):
        assert VALID_ASPECT_RATIOS == ["16:9", "4:3", "3:4", "9:16", "1:1"]


class TestLogUsage:
    def test_no_logging_when_disabled(self, sample_prompt, tiny_png_bytes, tmp_path):
        client = ImageClient(usage_log=None)
        mock_provider = _make_provider()
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        # Should not raise
        client.generate_image(sample_prompt, tmp_path)

    @patch("pixbridge._usage_log.log_usage")
    def test_logs_when_enabled(self, mock_log, sample_prompt, tiny_png_bytes, tmp_path):
        log_path = tmp_path / "usage.jsonl"
        client = ImageClient(usage_log=log_path)
        mock_provider = _make_provider()
        mock_provider.generate.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        client.generate_image(sample_prompt, tmp_path)

        mock_log.assert_called_once()
        entry = mock_log.call_args[0][1]
        assert entry["provider"] == "mock"
        assert entry["method"] == "generate_image"
        assert "duration_s" in entry

    @patch("pixbridge._usage_log.log_usage")
    def test_logs_style_transfer(self, mock_log, tiny_png_bytes, tmp_path):
        log_path = tmp_path / "usage.jsonl"
        client = ImageClient(usage_log=log_path)
        mock_provider = _make_provider(supports_style_transfer=True)
        mock_provider.style_transfer.return_value = GenerationResult(
            image_data=tiny_png_bytes,
            mime_type="image/png",
            provider="mock",
            model="m",
            metadata={},
        )
        client._provider = mock_provider

        input_img = tmp_path / "input.png"
        Image.new("RGB", (10, 10)).save(input_img)

        client.style_transfer_image(input_img, "raw style")

        mock_log.assert_called_once()
        entry = mock_log.call_args[0][1]
        assert entry["method"] == "style_transfer_image"

    @patch("pixbridge._usage_log.log_usage")
    def test_logs_generate_with_references(self, mock_log, sample_prompt, tiny_png_bytes, tmp_path):
        log_path = tmp_path / "usage.jsonl"
        client = ImageClient(usage_log=log_path)
        mock_provider = _make_provider(supports_reference_images=True)
        mock_provider.generate_with_references.return_value = _make_result(tiny_png_bytes)
        client._provider = mock_provider

        refs = [tmp_path / "ref.png"]
        client.generate_image_with_references(sample_prompt, refs, tmp_path / "out")

        entry = mock_log.call_args[0][1]
        assert entry["method"] == "generate_image_with_references"


class TestSaveImage:
    def test_saves_with_uuid_filename(self, tiny_png_bytes, tmp_path):
        client = ImageClient()
        result = GenerationResult(
            image_data=tiny_png_bytes,
            mime_type="image/png",
            provider="test",
            model="m",
        )

        path = client._save_image(result, tmp_path)

        assert path.exists()
        assert path.name.startswith("generated_")
        assert path.suffix == ".png"

    def test_jpeg_extension(self, tmp_path):
        # Create a small JPEG
        img = Image.new("RGB", (1, 1), "blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")

        client = ImageClient()
        result = GenerationResult(
            image_data=buf.getvalue(),
            mime_type="image/jpeg",
            provider="test",
            model="m",
        )

        path = client._save_image(result, tmp_path)

        assert path.suffix == ".jpg"
