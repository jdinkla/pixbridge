"""Tests for pixbridge.providers.base — BaseImageProvider helpers."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from pixbridge.models import GenerationNotes, ImagePrompt
from pixbridge.providers.base import (
    BaseImageProvider,
    GenerationResult,
    ImageProvider,
    ProviderCapabilities,
)


class ConcreteProvider(BaseImageProvider):
    """Minimal concrete subclass for testing abstract base."""

    @property
    def name(self) -> str:
        return "test-provider"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            sizes=["1K", "2K"],
            aspect_ratios=["16:9", "4:3", "1:1"],
            quality_levels=["low", "high"],
            default_model="model-a",
            default_size="1K",
            default_aspect_ratio="16:9",
            default_quality="low",
        )

    def generate(self, prompt, model=None, size=None, aspect_ratio=None, quality=None):
        return GenerationResult(
            image_data=b"fake-image",
            mime_type="image/png",
            provider=self.name,
            model=model or "model-a",
        )


class TestGenerationResult:
    def test_defaults(self):
        r = GenerationResult(
            image_data=b"data",
            mime_type="image/png",
            provider="test",
            model="m",
        )
        assert r.metadata == {}

    def test_with_metadata(self):
        r = GenerationResult(
            image_data=b"data",
            mime_type="image/jpeg",
            provider="gemini",
            model="m",
            metadata={"size": "2K"},
        )
        assert r.metadata["size"] == "2K"


class TestProviderCapabilities:
    def test_defaults(self):
        caps = ProviderCapabilities(sizes=[], aspect_ratios=[])
        assert caps.quality_levels is None
        assert caps.default_model is None
        assert caps.max_prompt_length is None
        assert caps.supports_style_transfer is False
        assert caps.supports_reference_images is False

    def test_max_prompt_length_can_be_set(self):
        caps = ProviderCapabilities(sizes=[], aspect_ratios=[], max_prompt_length=32000)
        assert caps.max_prompt_length == 32000

    def test_all_fields(self, gemini_capabilities):
        assert gemini_capabilities.supports_style_transfer is True
        assert gemini_capabilities.supports_reference_images is True
        assert "1K" in gemini_capabilities.sizes


class TestImageProviderProtocol:
    def test_concrete_provider_satisfies_protocol(self):
        provider = ConcreteProvider()
        assert isinstance(provider, ImageProvider)


class TestValidateParams:
    def test_valid_params(self):
        p = ConcreteProvider()
        p.validate_params(model="model-a", size="1K", aspect_ratio="16:9", quality="low")

    def test_all_none_accepted(self):
        p = ConcreteProvider()
        p.validate_params()

    def test_any_model_accepted(self):
        p = ConcreteProvider()
        p.validate_params(model="any-new-model")

    def test_invalid_size(self):
        p = ConcreteProvider()
        with pytest.raises(ValueError, match="Invalid size"):
            p.validate_params(size="4K")

    def test_invalid_aspect_ratio(self):
        p = ConcreteProvider()
        with pytest.raises(ValueError, match="Invalid aspect ratio"):
            p.validate_params(aspect_ratio="21:9")

    def test_invalid_quality(self):
        p = ConcreteProvider()
        with pytest.raises(ValueError, match="Invalid quality"):
            p.validate_params(quality="ultra")

    def test_quality_not_supported(self):
        """Provider without quality_levels rejects quality parameter."""

        class NoQualityProvider(ConcreteProvider):
            @property
            def capabilities(self):
                return ProviderCapabilities(
                    sizes=["1K"],
                    aspect_ratios=["16:9"],
                    quality_levels=None,
                )

        p = NoQualityProvider()
        with pytest.raises(ValueError, match="does not support quality"):
            p.validate_params(quality="high")

    def test_empty_sizes_skips_validation(self):
        """When sizes list is empty, any size is accepted."""

        class EmptySizesProvider(ConcreteProvider):
            @property
            def capabilities(self):
                return ProviderCapabilities(sizes=[], aspect_ratios=[])

        p = EmptySizesProvider()
        p.validate_params(size="anything")


class TestGetApiKey:
    def test_returns_stored_key(self):
        p = ConcreteProvider(api_key="stored-key")
        assert p._get_api_key(["SOME_VAR"]) == "stored-key"

    def test_falls_back_to_env_var(self):
        p = ConcreteProvider()
        with patch.dict(os.environ, {"MY_IMG_KEY": "env-value"}):
            assert p._get_api_key(["MY_IMG_KEY"]) == "env-value"

    def test_tries_multiple_env_vars(self):
        p = ConcreteProvider()
        with patch.dict(os.environ, {"SECOND_KEY": "found"}, clear=False):
            result = p._get_api_key(["MISSING_KEY_XYZ", "SECOND_KEY"])
            assert result == "found"

    def test_raises_when_no_key(self):
        p = ConcreteProvider()
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="API key required"),
        ):
            p._get_api_key(["NOPE"])

    def test_stored_key_takes_precedence_over_env(self):
        p = ConcreteProvider(api_key="stored")
        with patch.dict(os.environ, {"MY_KEY": "env"}):
            assert p._get_api_key(["MY_KEY"]) == "stored"


class TestMimeToExtension:
    def test_png(self):
        assert BaseImageProvider.mime_to_extension("image/png") == ".png"

    def test_jpeg(self):
        assert BaseImageProvider.mime_to_extension("image/jpeg") == ".jpg"

    def test_webp(self):
        assert BaseImageProvider.mime_to_extension("image/webp") == ".webp"

    def test_gif(self):
        assert BaseImageProvider.mime_to_extension("image/gif") == ".gif"

    def test_unknown_defaults_to_png(self):
        assert BaseImageProvider.mime_to_extension("image/bmp") == ".png"


class TestStyleTransferDefault:
    def test_raises_not_implemented(self):
        p = ConcreteProvider()
        with pytest.raises(NotImplementedError, match="does not support style transfer"):
            p.style_transfer(Path("img.png"), "style prompt")


class TestGenerateWithReferencesDefault:
    def test_raises_not_implemented(self):
        p = ConcreteProvider()
        with pytest.raises(NotImplementedError, match="does not support reference images"):
            p.generate_with_references(
                ImagePrompt(
                    full_prompt="test",
                    generation_notes=GenerationNotes(
                        aspect_ratio="16:9", key_requirements=[],
                    ),
                ),
                reference_images=[Path("ref.png")],
            )
