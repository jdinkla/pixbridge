"""OpenAI image generation provider."""

from __future__ import annotations

import base64
import logging
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal, cast

import requests
from openai import OpenAI

from ..models import ImagePrompt
from .base import BaseImageProvider, GenerationResult, ProviderCapabilities

logger = logging.getLogger(__name__)


# Mapping from named aspect ratios to OpenAI WxH sizes.
#
# `16:9` and `9:16` use the true-ratio sizes (2048x1152, 1152x2048). Earlier
# versions mapped these to 1536x1024 / 1024x1536, which are actually 3:2 / 2:3
# — those values remain available via the explicit `3:2` and `2:3` keys for
# callers who want the legacy behavior.
ASPECT_RATIO_TO_SIZE = {
    "16:9": "2048x1152",
    "9:16": "1152x2048",
    "4:3": "1536x1024",
    "3:4": "1024x1536",
    "3:2": "1536x1024",
    "2:3": "1024x1536",
    "1:1": "1024x1024",
}


# OpenAI gpt-image-2 accepts arbitrary WxH where both dimensions are divisible
# by 16, the aspect ratio is in [1:3, 3:1], and max(W, H) ≤ 3840. We expose
# this as rule-based validation rather than a closed allowlist so callers can
# pick true vertical/horizontal sizes (e.g. 1152x2048 for 9:16 shorts).
_OPENAI_WXH_RE = re.compile(r"^(\d+)x(\d+)$")
_OPENAI_MIN_RATIO = Fraction(1, 3)
_OPENAI_MAX_RATIO = Fraction(3, 1)
_OPENAI_MAX_DIM = 3840
_OPENAI_DIM_MULTIPLE = 16

# Recommended sizes — surfaced via ProviderCapabilities.sizes for docs and
# autocompletion. Any rule-conformant WxH is accepted; this list is illustrative.
_OPENAI_RECOMMENDED_SIZES = [
    "1024x1024",
    "1024x1536",
    "1536x1024",
    "1152x2048",
    "2048x1152",
    "2560x1440",
    "3840x2160",
]


def validate_openai_size(size: str) -> None:
    """Raise ValueError if `size` is not a valid OpenAI gpt-image-2 WxH string.

    Rules: both dimensions divisible by 16, aspect ratio in [1:3, 3:1],
    max(W, H) ≤ 3840.
    """
    m = _OPENAI_WXH_RE.match(size)
    if not m:
        raise ValueError(
            f"Invalid OpenAI size '{size}': expected WxH format like '1152x2048'."
        )
    w, h = int(m.group(1)), int(m.group(2))
    if w <= 0 or h <= 0:
        raise ValueError(f"Invalid OpenAI size '{size}': dimensions must be positive.")
    if w % _OPENAI_DIM_MULTIPLE or h % _OPENAI_DIM_MULTIPLE:
        raise ValueError(
            f"Invalid OpenAI size '{size}': both dimensions must be divisible by "
            f"{_OPENAI_DIM_MULTIPLE}."
        )
    if max(w, h) > _OPENAI_MAX_DIM:
        raise ValueError(
            f"Invalid OpenAI size '{size}': max dimension is {_OPENAI_MAX_DIM} "
            f"(got {max(w, h)})."
        )
    ratio = Fraction(w, h)
    if ratio < _OPENAI_MIN_RATIO or ratio > _OPENAI_MAX_RATIO:
        raise ValueError(
            f"Invalid OpenAI size '{size}': aspect ratio {w}:{h} is outside the "
            f"supported range [1:3, 3:1]."
        )


def is_valid_openai_size(size: str) -> bool:
    """Return True if `size` passes :func:`validate_openai_size`."""
    try:
        validate_openai_size(size)
    except ValueError:
        return False
    return True


# Capability surface for OpenAI. `sizes` is the recommended list (for docs /
# autocompletion); actual validation is rule-based via `size_validator`. Named
# aspect ratios map to explicit WxH sizes, and `max_dimension` documents the
# 3840px ceiling. Shared via OpenAIProvider.capabilities and the providers
# registry's get_capabilities() — no credentials needed to read it.
OPENAI_CAPABILITIES = ProviderCapabilities(
    sizes=list(_OPENAI_RECOMMENDED_SIZES),
    aspect_ratios=list(ASPECT_RATIO_TO_SIZE.keys()),
    quality_levels=["low", "medium", "high", "auto"],
    supported_models=["gpt-image-2"],
    default_size="1024x1024",
    default_aspect_ratio="1:1",
    default_quality="low",
    max_prompt_length=32000,
    supports_style_transfer=True,
    supports_reference_images=True,
    aspect_size_map=dict(ASPECT_RATIO_TO_SIZE),
    max_dimension=_OPENAI_MAX_DIM,
    size_validator=validate_openai_size,
)


class OpenAIProvider(BaseImageProvider):
    """Image generation provider using OpenAI's API."""

    ENV_KEYS = ["OPENAI_API_KEY"]

    def __init__(self, api_key: str | None = None):
        """Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key. If not provided, reads from
                     OPENAI_API_KEY environment variable.
        """
        super().__init__(api_key)
        self._client: OpenAI | None = None

    @property
    def name(self) -> str:
        return "openai"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # `sizes` is a list of recommended sizes (used for docs / autocompletion).
        # Actual validation uses :func:`validate_openai_size` via the capability
        # surface's `size_validator` — any WxH meeting the gpt-image-2 rules is
        # accepted. See OPENAI_CAPABILITIES.
        return OPENAI_CAPABILITIES

    _OUTPUT_FORMAT_TO_MIME = {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
    }

    @staticmethod
    def _normalize_output_format(output_format: str | None) -> str | None:
        """Coerce 'jpg' to 'jpeg' to match the OpenAI API's accepted values."""
        if output_format is None:
            return None
        fmt = output_format.lower()
        if fmt == "jpg":
            fmt = "jpeg"
        if fmt not in OpenAIProvider._OUTPUT_FORMAT_TO_MIME:
            raise ValueError(
                f"Invalid output_format '{output_format}'. "
                f"Must be one of: {list(OpenAIProvider._OUTPUT_FORMAT_TO_MIME)}"
            )
        return fmt

    def _get_client(self) -> OpenAI:
        """Get or create the OpenAI client."""
        if self._client is None:
            api_key = self._get_api_key(self.ENV_KEYS)
            self._client = OpenAI(api_key=api_key)
        return self._client

    # Section headers in anime prompts, in typical order
    _SECTION_HEADERS = [
        "GOAL:", "SCENE:", "BLOCKING:", "CHARACTERS IN FRAME:",
        "SETTING:", "STYLE:", "FIDELITY:", "CONSISTENCY:", "CONSISTENCY LOCK:",
    ]
    # Sections safe to compress (the three biggest in anime prompts)
    _COMPRESSIBLE_SECTIONS = {"CHARACTERS IN FRAME:", "SETTING:", "STYLE:"}

    @staticmethod
    def _truncate_prompt(prompt_text: str, max_length: int) -> str:
        """Truncate a prompt to fit within max_length, preserving structure.

        Parses the prompt by section headers and proportionally trims the
        compressible sections (CHARACTERS IN FRAME, SETTING, STYLE) from
        the end. Falls back to hard truncation if no headers are found.
        """
        if len(prompt_text) <= max_length:
            return prompt_text

        # Build regex to split on known section headers
        header_pattern = re.compile(
            r"^(" + "|".join(re.escape(h) for h in OpenAIProvider._SECTION_HEADERS) + ")",
            re.MULTILINE,
        )

        # Split into (header, content) pairs
        parts = header_pattern.split(prompt_text)
        # parts[0] is text before any header (preamble)
        # then alternating: header, content, header, content, ...

        if len(parts) < 3:
            # No recognized headers — hard-truncate as fallback
            return prompt_text[: max_length - 16] + "\n... [truncated]"

        # Build list of sections: (header_or_None, text, is_compressible)
        sections: list[tuple[str | None, str, bool]] = []
        # Preamble (before first header)
        if parts[0]:
            sections.append((None, parts[0], False))
        for i in range(1, len(parts), 2):
            header = parts[i]
            content = parts[i + 1] if i + 1 < len(parts) else ""
            compressible = header in OpenAIProvider._COMPRESSIBLE_SECTIONS
            sections.append((header, content, compressible))

        # Calculate sizes
        fixed_len = sum(
            len(h or "") + len(text)
            for h, text, comp in sections
            if not comp
        )
        compressible_sections = [
            (idx, len((h or "") + text))
            for idx, (h, text, comp) in enumerate(sections)
            if comp
        ]
        total_compressible = sum(size for _, size in compressible_sections)

        if total_compressible == 0:
            # Nothing compressible — hard-truncate
            return prompt_text[: max_length - 16] + "\n... [truncated]"

        # Budget for compressible sections (leave room for truncation markers)
        marker = "\n... [truncated]"
        marker_budget = len(marker) * len(compressible_sections)
        available = max_length - fixed_len - marker_budget
        if available < 0:
            # Even fixed content exceeds limit — hard-truncate
            return prompt_text[: max_length - 16] + "\n... [truncated]"

        # Distribute available space proportionally
        budgets: dict[int, int] = {}
        for idx, orig_size in compressible_sections:
            proportion = orig_size / total_compressible
            budgets[idx] = int(available * proportion)

        # Rebuild prompt
        result_parts: list[str] = []
        for idx, (header, text, comp) in enumerate(sections):
            if not comp:
                result_parts.append((header or "") + text)
            else:
                full = (header or "") + text
                budget = budgets[idx]
                if len(full) <= budget:
                    result_parts.append(full)
                else:
                    result_parts.append(full[:budget] + marker)

        return "".join(result_parts)

    def _aspect_ratio_to_size(self, aspect_ratio: str) -> str:
        """Convert aspect ratio to OpenAI size parameter.

        Args:
            aspect_ratio: Aspect ratio string (e.g., "16:9").

        Returns:
            OpenAI size string (e.g., "1536x1024").
        """
        return self.capabilities.aspect_to_size(aspect_ratio) or "1024x1024"

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
        """Generate an image using OpenAI API.

        Args:
            prompt: The ImagePrompt containing the full prompt.
            model: OpenAI model to use.
            size: Size dimensions. If aspect_ratio is provided, it takes precedence.
            aspect_ratio: Aspect ratio (maps to OpenAI size parameter).
            quality: Quality level (low, medium, high, auto).
            output_format: Output image format ('png', 'jpeg', 'webp'). Defaults
                to 'png' on the OpenAI side when None.
            output_compression: Compression level 0-100 for jpeg/webp. Ignored
                for png.

        Returns:
            GenerationResult with the generated image.
        """
        # Apply defaults
        caps = self.capabilities
        quality = quality or caps.default_quality
        if quality is None:
            raise RuntimeError("OpenAI provider has no default quality configured")

        # Determine size: aspect_ratio takes precedence if provided
        if aspect_ratio:
            size = self._aspect_ratio_to_size(aspect_ratio)
        else:
            size = size or caps.default_size
            aspect_ratio = caps.default_aspect_ratio
        if size is None:
            raise RuntimeError("OpenAI provider has no default size configured")

        # Validate parameters
        self.validate_params(model=model, size=size, quality=quality)
        assert model is not None  # narrowed: validate_params raises when None
        output_format = self._normalize_output_format(output_format)

        # Truncate prompt if it exceeds provider limit
        prompt_text = prompt.full_prompt
        original_length = len(prompt_text)
        prompt_truncated = False
        max_len = self.capabilities.max_prompt_length
        if max_len and original_length > max_len:
            prompt_text = self._truncate_prompt(prompt_text, max_len)
            prompt_truncated = True
            logger.warning(
                "Prompt truncated from %d to %d chars (limit %d)",
                original_length,
                len(prompt_text),
                max_len,
            )
            # Create a new ImagePrompt so we don't mutate the caller's object
            prompt = prompt.model_copy(update={"full_prompt": prompt_text})

        # Build kwargs and only include format/compression when supplied — the
        # SDK rejects None for these and png ignores compression entirely.
        extra_kwargs: dict = {}
        if output_format is not None:
            extra_kwargs["output_format"] = cast(
                "Literal['png', 'jpeg', 'webp']", output_format
            )
        if output_compression is not None and output_format in ("jpeg", "webp"):
            extra_kwargs["output_compression"] = output_compression

        # Generate the image. Size is validated rule-based above and passed as
        # an arbitrary WxH string — the SDK accepts any valid OpenAI size.
        client = self._get_client()
        response = client.images.generate(
            model=model,
            prompt=prompt.full_prompt,
            size=cast("Any", size),
            quality=cast("Literal['low', 'medium', 'high', 'auto']", quality),
            n=1,
            **extra_kwargs,
        )

        if not response.data:
            raise RuntimeError("OpenAI returned no image data")
        first = response.data[0]

        # Get image data - try b64_json first, fall back to URL download
        image_data: bytes
        image_url: str | None = None

        if hasattr(first, "b64_json") and first.b64_json:
            image_data = base64.b64decode(first.b64_json)
        elif hasattr(first, "url") and first.url:
            image_url = first.url
            image_response = requests.get(image_url, timeout=60)
            image_response.raise_for_status()
            image_data = image_response.content
        else:
            raise ValueError("No image data in OpenAI response")

        mime_type = self._OUTPUT_FORMAT_TO_MIME.get(
            output_format or "png", "image/png"
        )
        return GenerationResult(
            image_data=image_data,
            mime_type=mime_type,
            provider=self.name,
            model=model,
            metadata={
                "size": size,
                "aspect_ratio": aspect_ratio,
                "quality": quality,
                "output_format": output_format,
                "output_compression": output_compression,
                "revised_prompt": getattr(first, "revised_prompt", None),
                "image_url": image_url,
                "prompt_truncated": prompt_truncated,
                "original_prompt_length": original_length,
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
        """Generate an image with reference images via the OpenAI edits endpoint.

        Uses ``client.images.edit`` with multiple input images so gpt-image-2
        composes the new image while honoring the references for style /
        identity / brand consistency. The ``temperature`` parameter is accepted
        for API parity with other providers but ignored — the OpenAI image
        endpoint does not expose it.

        Args:
            prompt: The ImagePrompt containing the full prompt.
            reference_images: Paths to reference images. The OpenAI API accepts
                multiple images that are combined into a single generation.
            model: OpenAI model to use (defaults to provider default).
            size: Size dimensions. If aspect_ratio is provided, it takes precedence.
            aspect_ratio: Aspect ratio (maps to OpenAI size).
            quality: Quality level (low, medium, high, auto).
            temperature: Ignored (accepted for cross-provider parity).
            output_format: Output image format ('png', 'jpeg', 'webp').
            output_compression: Compression level 0-100 for jpeg/webp.

        Returns:
            GenerationResult with the generated image.
        """
        del temperature  # Unsupported by OpenAI image API; kept for parity.

        caps = self.capabilities
        quality = quality or caps.default_quality
        if quality is None:
            raise RuntimeError("OpenAI provider has no default quality configured")

        if aspect_ratio:
            size = self._aspect_ratio_to_size(aspect_ratio)
        else:
            size = size or caps.default_size
            aspect_ratio = caps.default_aspect_ratio
        if size is None:
            raise RuntimeError("OpenAI provider has no default size configured")

        self.validate_params(model=model, size=size, quality=quality)
        assert model is not None  # narrowed: validate_params raises when None
        output_format = self._normalize_output_format(output_format)

        # Truncate prompt if needed (same logic as generate())
        prompt_text = prompt.full_prompt
        original_length = len(prompt_text)
        prompt_truncated = False
        max_len = self.capabilities.max_prompt_length
        if max_len and original_length > max_len:
            prompt_text = self._truncate_prompt(prompt_text, max_len)
            prompt_truncated = True
            logger.warning(
                "Prompt truncated from %d to %d chars (limit %d)",
                original_length,
                len(prompt_text),
                max_len,
            )

        # Resolve reference paths and require existence — silent drops produce
        # surprisingly off-target output.
        existing_refs: list[Path] = []
        for ref in reference_images:
            ref_path = Path(ref)
            if not ref_path.exists():
                raise FileNotFoundError(f"Reference image not found: {ref_path}")
            existing_refs.append(ref_path)
        if not existing_refs:
            raise ValueError(
                "generate_with_references called with empty reference_images"
            )

        extra_kwargs: dict = {}
        if output_format is not None:
            extra_kwargs["output_format"] = cast(
                "Literal['png', 'jpeg', 'webp']", output_format
            )
        if output_compression is not None and output_format in ("jpeg", "webp"):
            extra_kwargs["output_compression"] = output_compression

        client = self._get_client()
        # Open all reference files for the duration of the API call.
        opened_files = [p.open("rb") for p in existing_refs]
        try:
            response = client.images.edit(
                model=model,
                image=opened_files,
                prompt=prompt_text,
                size=cast("Any", size),
                quality=cast("Literal['low', 'medium', 'high', 'auto']", quality),
                n=1,
                **extra_kwargs,
            )
        finally:
            for fh in opened_files:
                fh.close()

        if not response.data:
            raise RuntimeError("OpenAI returned no image data (edit)")
        first = response.data[0]

        image_data: bytes
        image_url: str | None = None
        if hasattr(first, "b64_json") and first.b64_json:
            image_data = base64.b64decode(first.b64_json)
        elif hasattr(first, "url") and first.url:
            image_url = first.url
            image_response = requests.get(image_url, timeout=60)
            image_response.raise_for_status()
            image_data = image_response.content
        else:
            raise ValueError("No image data in OpenAI edit response")

        mime_type = self._OUTPUT_FORMAT_TO_MIME.get(
            output_format or "png", "image/png"
        )
        return GenerationResult(
            image_data=image_data,
            mime_type=mime_type,
            provider=self.name,
            model=model,
            metadata={
                "size": size,
                "aspect_ratio": aspect_ratio,
                "quality": quality,
                "output_format": output_format,
                "output_compression": output_compression,
                "reference_images": [str(p) for p in existing_refs],
                "revised_prompt": getattr(first, "revised_prompt", None),
                "image_url": image_url,
                "prompt_truncated": prompt_truncated,
                "original_prompt_length": original_length,
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
        """Apply a visual style to an existing image via OpenAI's edits endpoint.

        Thin wrapper around :meth:`generate_with_references` with a single
        reference image — the OpenAI Image API treats single-image edits the
        same way as multi-image composition.
        """
        from ..models import GenerationNotes as _GenerationNotes
        from ..models import ImagePrompt as _ImagePrompt

        wrapped_prompt = _ImagePrompt(
            full_prompt=style_prompt,
            generation_notes=_GenerationNotes(
                aspect_ratio=aspect_ratio or "1:1",
                key_requirements=[],
            ),
        )
        return self.generate_with_references(
            prompt=wrapped_prompt,
            reference_images=[input_image],
            model=model,
            size=size,
            aspect_ratio=aspect_ratio,
        )
