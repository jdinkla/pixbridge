"""Shared fixtures for pixbridge tests."""

import pytest
from PIL import Image

from pixbridge.models import GenerationNotes, ImagePrompt, ImagePromptSections
from pixbridge.providers.base import GenerationResult, ProviderCapabilities


@pytest.fixture
def sample_prompt() -> ImagePrompt:
    return ImagePrompt(
        full_prompt="A serene mountain landscape at sunset with dramatic clouds",
        generation_notes=GenerationNotes(
            aspect_ratio="16:9",
            key_requirements=["photorealistic", "landscape"],
        ),
    )


@pytest.fixture
def sample_prompt_with_sections() -> ImagePrompt:
    return ImagePrompt(
        full_prompt="A serene mountain landscape at sunset",
        sections=ImagePromptSections(
            goal="Create a photorealistic mountain landscape",
            subject="Mountain range with snow-capped peaks",
            composition="Wide panoramic view with foreground wildflowers",
            setting="Alpine meadow at golden hour",
            lighting="Warm sunset light with long shadows",
            text_elements=None,
            style="Photorealistic, National Geographic quality",
            fidelity="Ultra-high detail, 8K texture resolution",
            consistency="Consistent warm color palette throughout",
        ),
        generation_notes=GenerationNotes(
            aspect_ratio="16:9",
            negative_prompts=["cartoon", "low quality"],
            key_requirements=["photorealistic", "landscape"],
        ),
    )


@pytest.fixture
def sample_generation_result() -> GenerationResult:
    # Minimal valid PNG: 1x1 pixel
    img = Image.new("RGB", (1, 1), color="red")
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    return GenerationResult(
        image_data=png_bytes,
        mime_type="image/png",
        provider="test",
        model="test-model",
        metadata={"size": "1K", "aspect_ratio": "16:9"},
    )


@pytest.fixture
def gemini_capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        sizes=["1K", "2K"],
        aspect_ratios=["16:9", "4:3", "3:4", "9:16", "1:1"],
        quality_levels=None,
        default_model="gemini-3-pro-image-preview",
        default_size="1K",
        default_aspect_ratio="16:9",
        supports_style_transfer=True,
        supports_reference_images=True,
    )


@pytest.fixture
def openai_capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        sizes=["1024x1024", "1024x1536", "1536x1024", "2560x1440", "3840x2160"],
        aspect_ratios=["16:9", "4:3", "3:4", "9:16", "1:1"],
        quality_levels=["low", "medium", "high"],
        default_model="gpt-image-2",
        default_size="1024x1024",
        default_aspect_ratio="1:1",
        default_quality="low",
        max_prompt_length=32000,
    )


@pytest.fixture
def xai_capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        sizes=[],
        aspect_ratios=["20:9", "16:9", "4:3", "3:2", "1:1"],
        quality_levels=None,
        default_model="grok-imagine-image",
        default_size=None,
        default_aspect_ratio="16:9",
    )


@pytest.fixture
def tiny_png_bytes() -> bytes:
    """A minimal valid PNG image (1x1 red pixel)."""
    img = Image.new("RGB", (1, 1), color="red")
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
