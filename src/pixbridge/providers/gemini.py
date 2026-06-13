"""Gemini image generation provider."""

import base64
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from PIL import Image

from ..models import ImagePrompt
from .base import BaseImageProvider, GenerationResult, ProviderCapabilities


def _extract_image_part(
    response: types.GenerateContentResponse, context: str
) -> tuple[bytes, str]:
    """Walk the Gemini response and return (image_bytes, mime_type).

    Raises RuntimeError if the response does not contain inline image data.
    """
    if not response.candidates:
        raise RuntimeError(f"Gemini returned no candidates ({context})")
    content = response.candidates[0].content
    if content is None or content.parts is None:
        raise RuntimeError(f"Gemini returned empty content ({context})")

    for part in content.parts:
        inline = getattr(part, "inline_data", None)
        if inline is None:
            continue
        data = inline.data
        mime_type = inline.mime_type
        if data is None or mime_type is None:
            continue
        if isinstance(data, str):
            data = base64.b64decode(data)
        return data, mime_type

    raise ValueError(f"No image found in Gemini response ({context})")


def _gemini_bucket(w: int, h: int) -> str:
    """Map raw WxH dimensions onto Gemini's named size tokens (1K / 2K)."""
    return "2K" if max(w, h) > 1024 else "1K"


# Capability surface for Gemini. Sizes are the named tokens 1K/2K (closed list,
# so `validate_size` checks membership); raw WxH dimensions are bucketed onto
# them via `size_bucketer`. Gemini takes the aspect ratio directly, so there's
# no aspect→WxH map and no single max-dimension limit. Shared via
# GeminiProvider.capabilities, the registry's get_capabilities(), and inherited
# by VertexProvider.
GEMINI_CAPABILITIES = ProviderCapabilities(
    sizes=["1K", "2K"],
    aspect_ratios=["16:9", "4:3", "3:4", "9:16", "1:1"],
    quality_levels=None,
    default_size="1K",
    default_aspect_ratio="16:9",
    supports_style_transfer=True,
    supports_reference_images=True,
    size_bucketer=_gemini_bucket,
)


class GeminiProvider(BaseImageProvider):
    """Image generation provider using Google's Gemini API."""

    ENV_KEYS = ["GOOGLE_API_KEY", "GEMINI_API_KEY"]

    def __init__(self, api_key: str | None = None):
        """Initialize the Gemini provider.

        Args:
            api_key: Gemini API key. If not provided, reads from
                     GOOGLE_API_KEY or GEMINI_API_KEY environment variables.
        """
        super().__init__(api_key)
        self._client: genai.Client | None = None

    @property
    def name(self) -> str:
        return "gemini"

    STYLE_TRANSFER_MODEL = "gemini-3-pro-image-preview"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return GEMINI_CAPABILITIES

    def _get_client(self) -> genai.Client:
        """Get or create the Gemini client."""
        if self._client is None:
            api_key = self._get_api_key(self.ENV_KEYS)
            self._client = genai.Client(api_key=api_key)
        return self._client

    def generate(
        self,
        prompt: ImagePrompt,
        model: str | None = None,
        size: str | None = None,
        aspect_ratio: str | None = None,
        quality: str | None = None,
        output_format: str | None = None,
        output_compression: int | None = None,
    ) -> GenerationResult:
        """Generate an image using Gemini API.

        Args:
            prompt: The ImagePrompt containing the full prompt.
            model: Gemini model to use.
            size: Size preset (1K, 2K).
            aspect_ratio: Aspect ratio (16:9, 4:3, 3:4, 9:16, 1:1).
            quality: Not supported by Gemini, will be ignored if provided.
            output_format: Not supported by Gemini, ignored. Accepted for cross-provider parity.
            output_compression: Not supported by Gemini, ignored.

        Returns:
            GenerationResult with the generated image.
        """
        del output_format, output_compression  # Unsupported by Gemini.
        # Apply defaults
        caps = self.capabilities
        size = size or caps.default_size
        aspect_ratio = aspect_ratio or caps.default_aspect_ratio

        # Validate parameters (raises if no model was specified)
        self.validate_params(model=model, size=size, aspect_ratio=aspect_ratio)

        # Generate the image
        client = self._get_client()
        response = client.models.generate_content(
            model=model,
            contents=prompt.full_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size=size,
                ),
            ),
        )

        image_data, mime_type = _extract_image_part(response, "generate")
        return GenerationResult(
            image_data=image_data,
            mime_type=mime_type,
            provider=self.name,
            model=model,
            metadata={
                "size": size,
                "aspect_ratio": aspect_ratio,
            },
        )

    def generate_with_references(
        self,
        prompt: ImagePrompt,
        reference_images: list[Path],
        model: str | None = None,
        size: str | None = None,
        aspect_ratio: str | None = None,
        quality: str | None = None,
        temperature: float | None = None,
        output_format: str | None = None,
        output_compression: int | None = None,
    ) -> GenerationResult:
        """Generate an image with reference images for identity consistency.

        Loads reference images as PIL objects and passes them alongside the
        text prompt in a single multimodal request, enabling Gemini's
        cross-attention to lock visual identity.

        Args:
            prompt: The ImagePrompt containing the full prompt.
            reference_images: Paths to reference sheet images (max 6 used).
            model: Gemini model to use.
            size: Size preset (1K, 2K).
            aspect_ratio: Aspect ratio for the output.
            quality: Not supported by Gemini.
            temperature: Generation temperature (default: 0.1 for consistency).
            output_format: Not supported by Gemini, ignored.
            output_compression: Not supported by Gemini, ignored.

        Returns:
            GenerationResult with the generated image.
        """
        del output_format, output_compression  # Unsupported by Gemini.
        caps = self.capabilities
        size = size or caps.default_size
        aspect_ratio = aspect_ratio or caps.default_aspect_ratio
        temperature = temperature if temperature is not None else 0.1

        self.validate_params(model=model, size=size, aspect_ratio=aspect_ratio)

        # Load reference images as PIL (cap at 6 for optimal identity focus)
        pil_refs = []
        for ref_path in reference_images[:6]:
            if ref_path.exists():
                pil_refs.append(Image.open(ref_path))

        # Build multimodal contents: reference images first, then text prompt.
        # Typed as Any because google-genai accepts PIL Image at runtime but
        # its type stubs don't include PIL in the contents union.
        contents: Any = [*pil_refs, prompt.full_prompt]

        client = self._get_client()
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                temperature=temperature,
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size=size,
                ),
            ),
        )

        image_data, mime_type = _extract_image_part(
            response, "generate_with_references"
        )
        return GenerationResult(
            image_data=image_data,
            mime_type=mime_type,
            provider=self.name,
            model=model,
            metadata={
                "size": size,
                "aspect_ratio": aspect_ratio,
                "reference_images": [str(p) for p in reference_images[:6]],
                "temperature": temperature,
            },
        )

    def style_transfer(
        self,
        input_image: Path,
        style_prompt: str,
        model: str | None = None,
        size: str | None = None,
        aspect_ratio: str | None = None,
    ) -> GenerationResult:
        """Apply a visual style to an existing image using Gemini's multimodal API.

        Args:
            input_image: Path to the input image file.
            style_prompt: Text describing the desired visual style.
            model: Gemini model to use (default: gemini-3-pro-image-preview).
            size: Size preset (1K, 2K).
            aspect_ratio: Aspect ratio for the output.

        Returns:
            GenerationResult with the styled image.
        """
        caps = self.capabilities
        model = model or self.STYLE_TRANSFER_MODEL
        size = size or caps.default_size
        aspect_ratio = aspect_ratio or caps.default_aspect_ratio

        self.validate_params(model=model, size=size, aspect_ratio=aspect_ratio)

        # Load input image as PIL Image (the SDK handles conversion)
        pil_image = Image.open(input_image)

        # Typed as Any because google-genai accepts PIL Image at runtime but
        # its type stubs don't include PIL in the contents union.
        contents: Any = [pil_image, style_prompt]

        client = self._get_client()
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size=size,
                ),
            ),
        )

        image_data, result_mime = _extract_image_part(response, "style_transfer")
        return GenerationResult(
            image_data=image_data,
            mime_type=result_mime,
            provider=self.name,
            model=model,
            metadata={
                "size": size,
                "aspect_ratio": aspect_ratio,
                "style_transfer": True,
                "input_image": str(input_image),
            },
        )
