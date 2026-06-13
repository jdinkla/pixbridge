"""Base classes and protocols for image generation providers."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..models import ImagePrompt


@dataclass
class GenerationResult:
    """Result of an image generation request."""

    image_data: bytes
    mime_type: str
    provider: str
    model: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ProviderCapabilities:
    """Capabilities and constraints for a provider.

    Besides holding declarative data (``sizes``, ``aspect_ratios``, …) this is
    the uniform *capability surface* every provider exposes: the
    :meth:`validate_size`, :meth:`recommended_sizes`, :meth:`aspect_to_size`,
    :meth:`max_dim`, and :meth:`native_size` methods let shared code reason
    about a provider's size rules without branching on the provider name.

    Provider-specific behavior is injected as data rather than hardcoded in
    callers:

    - ``size_validator`` — a rule-based validator (OpenAI: divisibility / ratio
      / max-dim). When ``None``, :meth:`validate_size` falls back to a
      closed-list check against ``sizes`` (Gemini's ``1K``/``2K``), and an
      empty ``sizes`` list means "no size constraint" (xAI).
    - ``size_bucketer`` — maps raw ``WxH`` dimensions onto a provider's native
      named size (Gemini buckets to ``1K``/``2K``). When ``None``,
      :meth:`native_size` validates and passes ``WxH`` through (OpenAI) or
      returns ``None`` for providers that only take an aspect ratio (xAI).
    - ``aspect_size_map`` — named aspect ratio → default ``WxH`` (OpenAI).
    """

    sizes: list[str]
    aspect_ratios: list[str]
    quality_levels: list[str] | None = None
    default_model: str | None = None
    default_size: str | None = None
    default_aspect_ratio: str | None = None
    default_quality: str | None = None
    max_prompt_length: int | None = None  # None = no known limit
    supports_style_transfer: bool = False
    supports_reference_images: bool = False
    # --- capability surface (TASK-42.2) ---
    aspect_size_map: dict[str, str] | None = None
    max_dimension: int | None = None
    size_validator: Callable[[str], None] | None = field(
        default=None, repr=False, compare=False
    )
    size_bucketer: Callable[[int, int], str | None] | None = field(
        default=None, repr=False, compare=False
    )

    def recommended_sizes(self) -> list[str]:
        """Sizes surfaced for docs / autocompletion.

        Not necessarily exhaustive — providers with rule-based validation
        (OpenAI) accept any conformant ``WxH`` beyond this list.
        """
        return list(self.sizes)

    def max_dim(self) -> int | None:
        """Largest dimension this provider accepts, or ``None`` if not bounded
        by a single pixel limit (e.g. Gemini/xAI use named sizes / ratios)."""
        return self.max_dimension

    def aspect_to_size(self, ratio: str) -> str | None:
        """Map a named aspect ratio to a default ``WxH``.

        Returns ``None`` for providers that don't translate ratios to explicit
        dimensions (Gemini passes the ratio to the API directly; xAI likewise).
        """
        if self.aspect_size_map is None:
            return None
        return self.aspect_size_map.get(ratio)

    def validate_size(self, size: str) -> None:
        """Validate a size string against this provider's rules.

        Raises:
            ValueError: If ``size`` is invalid for this provider.
        """
        if self.size_validator is not None:
            self.size_validator(size)
            return
        if self.sizes and size not in self.sizes:
            raise ValueError(
                f"Invalid size '{size}'. Must be one of: {self.sizes}"
            )
        # Empty `sizes` and no validator → size is unconstrained (xAI).

    def native_size(self, w: int, h: int) -> str | None:
        """Resolve raw ``WxH`` dimensions to this provider's native size token.

        - Bucketed providers (Gemini) map dimensions onto a named size.
        - Dimensional providers (OpenAI) validate and pass ``WxH`` through.
        - Ratio-only providers (xAI) return ``None``.

        Raises:
            ValueError: If the provider validates dimensions and they're invalid.
        """
        if self.size_bucketer is not None:
            return self.size_bucketer(w, h)
        if self.size_validator is not None:
            wxh = f"{w}x{h}"
            self.size_validator(wxh)
            return wxh
        return None


@runtime_checkable
class ImageProvider(Protocol):
    """Protocol for image generation providers."""

    @property
    def name(self) -> str:
        """Provider name identifier."""
        ...

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Provider capabilities and constraints."""
        ...

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
        """Generate an image from a prompt.

        Args:
            prompt: The ImagePrompt containing the full prompt and configuration.
            model: Model to use (provider-specific).
            size: Size preset or dimensions.
            aspect_ratio: Aspect ratio for the image.
            quality: Quality level (if supported by provider).
            output_format: Output format ('png', 'jpeg', 'webp'). Provider may
                ignore if unsupported.
            output_compression: Compression level 0-100 for jpeg/webp. Ignored
                for png and unsupported providers.

        Returns:
            GenerationResult with image data and metadata.
        """
        ...

    def validate_params(
        self,
        model: str | None = None,
        size: str | None = None,
        aspect_ratio: str | None = None,
        quality: str | None = None,
    ) -> None:
        """Validate generation parameters against provider capabilities.

        Raises:
            ValueError: If any parameter is invalid for this provider.
        """
        ...


class BaseImageProvider(ABC):
    """Abstract base class for image providers with common functionality."""

    def __init__(self, api_key: str | None = None):
        """Initialize the provider.

        Args:
            api_key: API key for the provider. If not provided,
                     reads from environment variables.
        """
        self._api_key = api_key

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Provider capabilities and constraints."""
        ...

    @abstractmethod
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
        """Generate an image from a prompt."""
        ...

    def style_transfer(
        self,
        input_image: Path,
        style_prompt: str,
        model: str | None = None,
        size: str | None = None,
        aspect_ratio: str | None = None,
    ) -> GenerationResult:
        """Apply a visual style to an existing image.

        Args:
            input_image: Path to the input image file.
            style_prompt: Text describing the desired visual style.
            model: Model to use (provider-specific).
            size: Size preset for the output.
            aspect_ratio: Aspect ratio for the output.

        Returns:
            GenerationResult with the styled image.

        Raises:
            NotImplementedError: If the provider doesn't support style transfer.
        """
        raise NotImplementedError(
            f"Provider {self.name} does not support style transfer"
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

        Args:
            prompt: The ImagePrompt containing the full prompt.
            reference_images: Paths to reference sheet images.
            model: Model to use (provider-specific).
            size: Size preset for the output.
            aspect_ratio: Aspect ratio for the output.
            quality: Quality level (if supported).
            temperature: Generation temperature (lower = more consistent).
            output_format: Output format ('png', 'jpeg', 'webp'). Provider may
                ignore if unsupported.
            output_compression: Compression level 0-100 for jpeg/webp. Ignored
                for png and unsupported providers.

        Returns:
            GenerationResult with the generated image.

        Raises:
            NotImplementedError: If the provider doesn't support reference images.
        """
        raise NotImplementedError(
            f"Provider {self.name} does not support reference images"
        )

    def validate_params(
        self,
        model: str | None = None,
        size: str | None = None,
        aspect_ratio: str | None = None,
        quality: str | None = None,
    ) -> None:
        """Validate generation parameters against provider capabilities.

        Raises:
            ValueError: If any parameter is invalid for this provider.
        """
        caps = self.capabilities

        if size is not None:
            caps.validate_size(size)

        if aspect_ratio is not None and caps.aspect_ratios and aspect_ratio not in caps.aspect_ratios:
            raise ValueError(
                f"Invalid aspect ratio '{aspect_ratio}' for {self.name}. "
                f"Must be one of: {caps.aspect_ratios}"
            )

        if quality is not None:
            if caps.quality_levels is None:
                raise ValueError(f"Provider {self.name} does not support quality parameter")
            if quality not in caps.quality_levels:
                raise ValueError(
                    f"Invalid quality '{quality}' for {self.name}. "
                    f"Must be one of: {caps.quality_levels}"
                )

    def _get_api_key(self, env_keys: list[str]) -> str:
        """Get API key from stored value or environment variables.

        Args:
            env_keys: List of environment variable names to check.

        Returns:
            The API key.

        Raises:
            ValueError: If no API key is found.
        """
        import os

        if self._api_key:
            return self._api_key

        for key in env_keys:
            value = os.environ.get(key)
            if value:
                return value

        raise ValueError(
            f"API key required for {self.name}. "
            f"Set one of {env_keys} environment variables, "
            "or pass api_key parameter."
        )

    @staticmethod
    def mime_to_extension(mime_type: str) -> str:
        """Convert MIME type to file extension."""
        mime_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        return mime_map.get(mime_type, ".png")
