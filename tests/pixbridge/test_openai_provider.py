"""Tests for pixbridge.providers.openai — OpenAIProvider with mocked SDK."""

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pixbridge.providers.openai import (
    ASPECT_RATIO_TO_SIZE,
    OpenAIProvider,
    is_valid_openai_size,
    validate_openai_size,
)


@pytest.fixture
def provider() -> OpenAIProvider:
    return OpenAIProvider(api_key="test-key")


def _make_openai_response(b64_json: str | None = None, url: str | None = None):
    """Build a mock OpenAI images.generate response."""
    data_item = SimpleNamespace(
        b64_json=b64_json,
        url=url,
        revised_prompt="revised prompt text",
    )
    return SimpleNamespace(data=[data_item])


class TestOpenAICapabilities:
    def test_name(self, provider):
        assert provider.name == "openai"

    def test_default_model(self, provider):
        caps = provider.capabilities
        assert caps.default_model == "gpt-image-2"

    def test_sizes(self, provider):
        caps = provider.capabilities
        # `sizes` is the list of *recommended* sizes — rule-based validation
        # accepts any conformant WxH beyond these.
        assert "1024x1024" in caps.sizes
        assert "1024x1536" in caps.sizes
        assert "1536x1024" in caps.sizes
        assert "1152x2048" in caps.sizes
        assert "2048x1152" in caps.sizes
        assert "2560x1440" in caps.sizes
        assert "3840x2160" in caps.sizes

    def test_quality_levels(self, provider):
        caps = provider.capabilities
        assert caps.quality_levels == ["low", "medium", "high", "auto"]
        assert caps.default_quality == "low"

    def test_supports_style_transfer(self, provider):
        # gpt-image-2 enables style transfer via the images.edit endpoint.
        assert provider.capabilities.supports_style_transfer is True

    def test_supports_reference_images(self, provider):
        # gpt-image-2 accepts multi-image input via images.edit.
        assert provider.capabilities.supports_reference_images is True


class TestAspectRatioToSize:
    def test_16_9(self, provider):
        # True 16:9 (was incorrectly 1536x1024 = 3:2 in older versions).
        assert provider._aspect_ratio_to_size("16:9") == "2048x1152"

    def test_9_16(self, provider):
        # True 9:16 (was incorrectly 1024x1536 = 2:3 in older versions).
        assert provider._aspect_ratio_to_size("9:16") == "1152x2048"

    def test_4_3(self, provider):
        assert provider._aspect_ratio_to_size("4:3") == "1536x1024"

    def test_3_4(self, provider):
        assert provider._aspect_ratio_to_size("3:4") == "1024x1536"

    def test_3_2_alias(self, provider):
        # Explicit alias for the legacy 16:9 → 1536x1024 mapping.
        assert provider._aspect_ratio_to_size("3:2") == "1536x1024"

    def test_2_3_alias(self, provider):
        # Explicit alias for the legacy 9:16 → 1024x1536 mapping.
        assert provider._aspect_ratio_to_size("2:3") == "1024x1536"

    def test_1_1(self, provider):
        assert provider._aspect_ratio_to_size("1:1") == "1024x1024"

    def test_unknown_defaults_to_square(self, provider):
        assert provider._aspect_ratio_to_size("21:9") == "1024x1024"

    def test_mapping_dict_complete(self):
        assert set(ASPECT_RATIO_TO_SIZE.keys()) == {
            "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "1:1",
        }


class TestValidateOpenAISize:
    @pytest.mark.parametrize("size", [
        "1024x1024",
        "1152x2048",   # true 9:16
        "2048x1152",   # true 16:9
        "720x1280",    # rule-based, not in recommended list
        "1088x1920",   # rule-based, not in recommended list
        "1536x1024",
        "2560x1440",
        "3840x2160",
        "1024x3072",   # ratio 1:3, lower bound
        "3072x1024",   # ratio 3:1, upper bound
    ])
    def test_valid_sizes_pass(self, size):
        validate_openai_size(size)
        assert is_valid_openai_size(size)

    @pytest.mark.parametrize("size,reason_fragment", [
        ("1080x1920", "divisible by 16"),    # 1080 not /16
        ("1920x1080", "divisible by 16"),    # 1080 not /16
        ("2048x512", "aspect ratio"),        # 4:1, exceeds 3:1
        ("512x2048", "aspect ratio"),        # 1:4, below 1:3
        ("4096x4096", "max dimension"),
        ("3856x2160", "max dimension"),      # one dim > 3840
        ("1024", "WxH format"),
        ("1024x1024x1024", "WxH format"),
        ("axb", "WxH format"),
        ("0x1024", "positive"),
    ])
    def test_invalid_sizes_raise(self, size, reason_fragment):
        with pytest.raises(ValueError, match=reason_fragment):
            validate_openai_size(size)
        assert not is_valid_openai_size(size)


class TestOpenAIGenerate:
    def test_b64_json_response(self, provider, sample_prompt, tiny_png_bytes):
        encoded = base64.b64encode(tiny_png_bytes).decode("ascii")
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_openai_response(
            b64_json=encoded,
        )
        provider._client = mock_client

        result = provider.generate(sample_prompt)

        assert result.image_data == tiny_png_bytes
        assert result.mime_type == "image/png"
        assert result.provider == "openai"
        assert result.model == "gpt-image-2"
        assert result.metadata["revised_prompt"] == "revised prompt text"

    @patch("pixbridge.providers.openai.requests.get")
    def test_url_response_fallback(self, mock_get, provider, sample_prompt, tiny_png_bytes):
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_openai_response(
            url="https://example.com/image.png",
        )
        provider._client = mock_client

        mock_response = MagicMock()
        mock_response.content = tiny_png_bytes
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = provider.generate(sample_prompt)

        assert result.image_data == tiny_png_bytes
        assert result.metadata["image_url"] == "https://example.com/image.png"
        mock_get.assert_called_once_with("https://example.com/image.png", timeout=60)

    def test_no_image_data_raises(self, provider, sample_prompt):
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_openai_response()
        provider._client = mock_client

        with pytest.raises(ValueError, match="No image data"):
            provider.generate(sample_prompt)

    def test_applies_defaults(self, provider, sample_prompt, tiny_png_bytes):
        encoded = base64.b64encode(tiny_png_bytes).decode("ascii")
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_openai_response(
            b64_json=encoded,
        )
        provider._client = mock_client

        result = provider.generate(sample_prompt)

        assert result.metadata["quality"] == "low"
        assert result.metadata["aspect_ratio"] == "1:1"

    def test_aspect_ratio_overrides_size(self, provider, sample_prompt, tiny_png_bytes):
        encoded = base64.b64encode(tiny_png_bytes).decode("ascii")
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_openai_response(
            b64_json=encoded,
        )
        provider._client = mock_client

        result = provider.generate(sample_prompt, aspect_ratio="16:9")

        # True 16:9 — was 1536x1024 (3:2) before the mapping was corrected.
        assert result.metadata["size"] == "2048x1152"

    def test_custom_model_and_quality(self, provider, sample_prompt, tiny_png_bytes):
        encoded = base64.b64encode(tiny_png_bytes).decode("ascii")
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_openai_response(
            b64_json=encoded,
        )
        provider._client = mock_client

        result = provider.generate(
            sample_prompt, model="gpt-image-1.5", quality="high",
        )

        assert result.model == "gpt-image-1.5"
        assert result.metadata["quality"] == "high"

    def test_invalid_quality_raises(self, provider, sample_prompt):
        with pytest.raises(ValueError, match="Invalid quality"):
            provider.generate(sample_prompt, quality="ultra")

    def test_output_format_passed_through(self, provider, sample_prompt, tiny_png_bytes):
        encoded = base64.b64encode(tiny_png_bytes).decode("ascii")
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_openai_response(
            b64_json=encoded,
        )
        provider._client = mock_client

        result = provider.generate(
            sample_prompt, output_format="webp", output_compression=85,
        )

        call_kwargs = mock_client.images.generate.call_args[1]
        assert call_kwargs["output_format"] == "webp"
        assert call_kwargs["output_compression"] == 85
        assert result.mime_type == "image/webp"
        assert result.metadata["output_format"] == "webp"

    def test_jpg_normalized_to_jpeg(self, provider, sample_prompt, tiny_png_bytes):
        encoded = base64.b64encode(tiny_png_bytes).decode("ascii")
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_openai_response(
            b64_json=encoded,
        )
        provider._client = mock_client

        result = provider.generate(sample_prompt, output_format="jpg")

        call_kwargs = mock_client.images.generate.call_args[1]
        assert call_kwargs["output_format"] == "jpeg"
        assert result.mime_type == "image/jpeg"

    def test_compression_dropped_for_png(self, provider, sample_prompt, tiny_png_bytes):
        encoded = base64.b64encode(tiny_png_bytes).decode("ascii")
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_openai_response(
            b64_json=encoded,
        )
        provider._client = mock_client

        provider.generate(sample_prompt, output_format="png", output_compression=50)

        call_kwargs = mock_client.images.generate.call_args[1]
        # PNG ignores compression — the SDK rejects it, so we don't pass it.
        assert "output_compression" not in call_kwargs

    def test_invalid_output_format_raises(self, provider, sample_prompt):
        with pytest.raises(ValueError, match="Invalid output_format"):
            provider.generate(sample_prompt, output_format="bmp")


class TestOpenAIGenerateWithReferences:
    def test_uses_edit_endpoint(self, provider, sample_prompt, tiny_png_bytes, tmp_path):
        encoded = base64.b64encode(tiny_png_bytes).decode("ascii")
        mock_client = MagicMock()
        mock_client.images.edit.return_value = _make_openai_response(
            b64_json=encoded,
        )
        provider._client = mock_client

        ref1 = tmp_path / "ref1.png"
        ref1.write_bytes(tiny_png_bytes)
        ref2 = tmp_path / "ref2.png"
        ref2.write_bytes(tiny_png_bytes)

        result = provider.generate_with_references(
            sample_prompt, reference_images=[ref1, ref2],
        )

        mock_client.images.edit.assert_called_once()
        call_kwargs = mock_client.images.edit.call_args[1]
        # `image` should be a list of file handles, one per reference
        assert isinstance(call_kwargs["image"], list)
        assert len(call_kwargs["image"]) == 2
        assert result.metadata["reference_images"] == [str(ref1), str(ref2)]

    def test_missing_reference_raises(self, provider, sample_prompt, tmp_path):
        with pytest.raises(FileNotFoundError, match="Reference image not found"):
            provider.generate_with_references(
                sample_prompt, reference_images=[tmp_path / "nope.png"],
            )

    def test_empty_references_raises(self, provider, sample_prompt):
        with pytest.raises(ValueError, match="empty reference_images"):
            provider.generate_with_references(sample_prompt, reference_images=[])

    def test_temperature_accepted_but_ignored(
        self, provider, sample_prompt, tiny_png_bytes, tmp_path,
    ):
        encoded = base64.b64encode(tiny_png_bytes).decode("ascii")
        mock_client = MagicMock()
        mock_client.images.edit.return_value = _make_openai_response(
            b64_json=encoded,
        )
        provider._client = mock_client

        ref = tmp_path / "ref.png"
        ref.write_bytes(tiny_png_bytes)

        provider.generate_with_references(
            sample_prompt, reference_images=[ref], temperature=0.3,
        )
        # temperature is not part of the OpenAI image API surface
        call_kwargs = mock_client.images.edit.call_args[1]
        assert "temperature" not in call_kwargs


class TestOpenAIStyleTransfer:
    def test_wraps_single_reference_edit(
        self, provider, tiny_png_bytes, tmp_path,
    ):
        encoded = base64.b64encode(tiny_png_bytes).decode("ascii")
        mock_client = MagicMock()
        mock_client.images.edit.return_value = _make_openai_response(
            b64_json=encoded,
        )
        provider._client = mock_client

        input_image = tmp_path / "input.png"
        input_image.write_bytes(tiny_png_bytes)

        result = provider.style_transfer(
            input_image=input_image,
            style_prompt="Restyle as 1920s film noir",
        )

        mock_client.images.edit.assert_called_once()
        call_kwargs = mock_client.images.edit.call_args[1]
        assert len(call_kwargs["image"]) == 1
        assert call_kwargs["prompt"] == "Restyle as 1920s film noir"
        assert result.provider == "openai"


class TestOpenAIGetClient:
    def test_lazy_init(self, provider):
        assert provider._client is None

    @patch("pixbridge.providers.openai.OpenAI")
    def test_creates_client_with_api_key(self, mock_cls, provider):
        mock_cls.return_value = MagicMock()
        client = provider._get_client()
        mock_cls.assert_called_once_with(api_key="test-key")
        assert client is not None

    @patch("pixbridge.providers.openai.OpenAI")
    def test_caches_client(self, mock_cls, provider):
        mock_cls.return_value = MagicMock()
        c1 = provider._get_client()
        c2 = provider._get_client()
        assert c1 is c2
        mock_cls.assert_called_once()


def _build_sectioned_prompt(
    char_len: int = 5000, setting_len: int = 5000, style_len: int = 4000,
) -> str:
    """Build a prompt with known section headers and padded content."""
    return (
        f"GOAL: Visual scene for anime frame 42 of 164.\n\n"
        f"SCENE: A tense confrontation in the castle courtyard.\n\n"
        f"BLOCKING:\n- Character A faces Character B\n\n"
        f"CHARACTERS IN FRAME:\n{'x' * char_len}\n\n"
        f"SETTING:\n{'y' * setting_len}\n\n"
        f"STYLE: {'z' * style_len}\n\n"
        f"FIDELITY: High quality anime illustration.\n\n"
        f"CONSISTENCY: Maintain character designs\n\n"
        f"CONSISTENCY LOCK: eye_color=blue hair=silver"
    )


class TestPromptTruncation:
    def test_short_prompt_unchanged(self):
        short = "GOAL: test\nSCENE: simple"
        result = OpenAIProvider._truncate_prompt(short, 32000)
        assert result == short

    def test_long_prompt_fits_within_limit(self):
        # Build a prompt well over 32K
        prompt = _build_sectioned_prompt(
            char_len=15000, setting_len=12000, style_len=8000,
        )
        assert len(prompt) > 32000

        result = OpenAIProvider._truncate_prompt(prompt, 32000)
        assert len(result) <= 32000

    def test_fixed_sections_preserved(self):
        prompt = _build_sectioned_prompt(
            char_len=15000, setting_len=12000, style_len=8000,
        )
        result = OpenAIProvider._truncate_prompt(prompt, 32000)

        # Fixed sections must survive intact
        assert "GOAL: Visual scene for anime frame 42 of 164." in result
        assert "FIDELITY: High quality anime illustration." in result
        assert "CONSISTENCY LOCK: eye_color=blue hair=silver" in result

    def test_truncated_sections_get_marker(self):
        prompt = _build_sectioned_prompt(
            char_len=15000, setting_len=12000, style_len=8000,
        )
        result = OpenAIProvider._truncate_prompt(prompt, 32000)
        assert "... [truncated]" in result

    def test_no_headers_hard_truncates(self):
        prompt = "A" * 40000
        result = OpenAIProvider._truncate_prompt(prompt, 32000)
        assert len(result) <= 32000
        assert result.endswith("... [truncated]")

    def test_preamble_before_first_header_preserved(self):
        # Text before the first recognized header is a fixed (non-compressible)
        # section and must survive proportional trimming.
        prompt = (
            "Preamble text before any headers.\n\n"
            "GOAL: brief goal\n\n"
            "SETTING: " + "s" * 500
        )
        result = OpenAIProvider._truncate_prompt(prompt, 200)
        assert len(result) <= 200
        assert "Preamble text before any headers." in result

    def test_headers_but_nothing_compressible_hard_truncates(self):
        # Only non-compressible sections present → no budget to redistribute,
        # so it falls back to a hard truncation.
        prompt = "GOAL: " + "g" * 300 + "\n\nFIDELITY: " + "f" * 300
        result = OpenAIProvider._truncate_prompt(prompt, 100)
        assert len(result) <= 100
        assert result.endswith("... [truncated]")

    def test_fixed_content_exceeds_limit_hard_truncates(self):
        # A compressible section exists, but the fixed content alone overruns the
        # limit (available budget goes negative) → hard truncation.
        prompt = "GOAL: " + "g" * 300 + "\n\nSETTING: " + "s" * 300
        result = OpenAIProvider._truncate_prompt(prompt, 100)
        assert len(result) <= 100
        assert result.endswith("... [truncated]")

    def test_max_prompt_length_capability(self, provider):
        assert provider.capabilities.max_prompt_length == 32000

    def test_generate_adds_truncation_metadata(
        self, provider, sample_prompt, tiny_png_bytes,
    ):
        """When prompt exceeds limit, metadata records truncation info."""
        long_prompt = _build_sectioned_prompt(
            char_len=15000, setting_len=12000, style_len=8000,
        )
        from pixbridge.models import GenerationNotes, ImagePrompt

        big_prompt = ImagePrompt(
            full_prompt=long_prompt,
            generation_notes=GenerationNotes(
                aspect_ratio="16:9", key_requirements=["anime"],
            ),
        )

        encoded = base64.b64encode(tiny_png_bytes).decode("ascii")
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_openai_response(
            b64_json=encoded,
        )
        provider._client = mock_client

        result = provider.generate(big_prompt)

        assert result.metadata["prompt_truncated"] is True
        assert result.metadata["original_prompt_length"] == len(long_prompt)
        # Verify the API was called with the truncated prompt
        call_kwargs = mock_client.images.generate.call_args[1]
        assert len(call_kwargs["prompt"]) <= 32000

    def test_generate_no_truncation_metadata(
        self, provider, sample_prompt, tiny_png_bytes,
    ):
        """Short prompts get prompt_truncated=False in metadata."""
        encoded = base64.b64encode(tiny_png_bytes).decode("ascii")
        mock_client = MagicMock()
        mock_client.images.generate.return_value = _make_openai_response(
            b64_json=encoded,
        )
        provider._client = mock_client

        result = provider.generate(sample_prompt)

        assert result.metadata["prompt_truncated"] is False
