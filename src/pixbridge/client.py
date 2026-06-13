"""Unified image generation client with multi-provider support."""

import io
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from .models import ImagePrompt
from .providers import get_provider, list_providers
from .providers.base import BaseImageProvider, GenerationResult
from .size_resolver import resolve_size_preset

#: Default location for style-transfer presets, relative to the current working
#: directory. Override per-instance with ``ImageClient(style_presets_dir=...)``
#: or globally with the ``PIXBRIDGE_STYLE_PRESETS_DIR`` environment variable.
DEFAULT_STYLE_PRESETS_DIR = Path("prompts/style-transfer")

#: Environment variable that overrides the style-preset directory.
STYLE_PRESETS_DIR_ENV = "PIXBRIDGE_STYLE_PRESETS_DIR"


def _resolve_presets_dir(preset_dir: Path | None = None) -> Path:
    """Resolve the style-preset directory.

    Resolution order: explicit ``preset_dir`` argument, then the
    ``PIXBRIDGE_STYLE_PRESETS_DIR`` environment variable, then
    :data:`DEFAULT_STYLE_PRESETS_DIR`.
    """
    if preset_dir is not None:
        return Path(preset_dir)
    env_dir = os.environ.get(STYLE_PRESETS_DIR_ENV)
    if env_dir:
        return Path(env_dir)
    return DEFAULT_STYLE_PRESETS_DIR


class ImageClient:
    """Unified client for image generation with multi-provider support."""

    def __init__(
        self,
        provider: str = "gemini",
        api_key: str | None = None,
        usage_log: Path | None = None,
        default_output_format: str | None = None,
        default_output_compression: int | None = None,
        default_reference_images: list[Path] | None = None,
        style_presets_dir: Path | None = None,
    ):
        """Initialize the image client.

        Args:
            provider: Provider name (gemini, openai, xai).
            api_key: Optional API key. If not provided, reads from
                     provider-specific environment variables.
            usage_log: Path to a JSONL file for logging usage.
                       Pass None to disable logging.
            default_output_format: Default output format ('png', 'jpeg', 'webp')
                used when generate_image() is called without an explicit one.
            default_output_compression: Default compression level 0-100 for
                jpeg/webp.
            default_reference_images: Default reference images applied to every
                generate_image() call. When non-empty (and the provider
                supports references), generate_image() is silently promoted to
                generate_image_with_references(). Per-call references on
                generate_image_with_references() always win.
            style_presets_dir: Directory holding style-transfer preset ``.md``
                files. When None, falls back to the
                ``PIXBRIDGE_STYLE_PRESETS_DIR`` environment variable, then to
                ``prompts/style-transfer`` relative to the current working
                directory.
        """
        self.provider_name = provider
        self._api_key = api_key
        self._provider: BaseImageProvider | None = None
        self.usage_log = usage_log
        self.default_output_format = default_output_format
        self.default_output_compression = default_output_compression
        self.default_reference_images: list[Path] = list(default_reference_images or [])
        self.style_presets_dir = style_presets_dir

    @property
    def provider(self) -> BaseImageProvider:
        """Get the provider instance (lazy initialization)."""
        if self._provider is None:
            self._provider = get_provider(self.provider_name, self._api_key)
        return self._provider

    @property
    def api_key(self) -> str | None:
        """Get the API key (for backward compatibility with pipeline)."""
        return self._api_key

    def _resolve_size(
        self,
        size: str | None,
        aspect_ratio: str | None,
    ) -> tuple[str | None, str | None]:
        """Resolve a size preset (720p, 1080p, 2160p, WxH) to provider-specific values.

        Returns the (size, aspect_ratio) tuple to pass to the provider. If the
        caller did not specify a size, both inputs are returned unchanged.
        """
        if size is None:
            return size, aspect_ratio
        resolved_size, resolved_aspect = resolve_size_preset(size, self.provider_name)
        if aspect_ratio is None and resolved_aspect is not None:
            aspect_ratio = resolved_aspect
        return resolved_size, aspect_ratio

    def _log_usage(
        self, method: str, duration_s: float, result: GenerationResult,
    ) -> None:
        """Log an image generation API call to the usage JSONL file."""
        if self.usage_log is None:
            return
        from ._usage_log import log_usage

        entry: dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "provider": result.provider,
            "model": result.model,
            "method": method,
            "task": "image",
            "duration_s": round(duration_s, 3),
        }
        entry.update(result.metadata)
        log_usage(self.usage_log, entry)

    def generate_image(
        self,
        prompt: ImagePrompt,
        output_dir: Path | str = "output",
        model: str | None = None,
        size: str | None = None,
        aspect_ratio: str | None = None,
        quality: str | None = None,
        output_format: str | None = None,
        output_compression: int | None = None,
    ) -> Path:
        """Generate an image from a prompt and save it.

        Args:
            prompt: The ImagePrompt containing the full prompt and configuration.
            output_dir: Directory to save the generated image.
            model: Model to use (provider-specific). Uses provider default if not specified.
            size: Size preset or dimensions. Uses provider default if not specified.
            aspect_ratio: Aspect ratio for the image.
            quality: Quality level (OpenAI only: low, medium, high, auto).
            output_format: Output image format ('png', 'jpeg', 'webp'). Provider
                may ignore if unsupported (gemini/xai/vertex always emit png).
            output_compression: Compression level 0-100 for jpeg/webp. Ignored
                for png and unsupported providers.

        Returns:
            Path to the saved image file.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        size, aspect_ratio = self._resolve_size(size, aspect_ratio)
        output_format = output_format or self.default_output_format
        if output_compression is None:
            output_compression = self.default_output_compression

        # Auto-promote to references when client has defaults configured and the
        # active provider supports them. Slide-pipeline use case: --ref-image is
        # set globally and every slide should use the same anchors.
        if (
            self.default_reference_images
            and self.provider.capabilities.supports_reference_images
        ):
            t0 = time.monotonic()
            result = self.provider.generate_with_references(
                prompt=prompt,
                reference_images=self.default_reference_images,
                model=model,
                size=size,
                aspect_ratio=aspect_ratio,
                quality=quality,
                output_format=output_format,
                output_compression=output_compression,
            )
            self._log_usage(
                "generate_image_with_references", time.monotonic() - t0, result,
            )
        else:
            t0 = time.monotonic()
            result = self.provider.generate(
                prompt=prompt,
                model=model,
                size=size,
                aspect_ratio=aspect_ratio,
                quality=quality,
                output_format=output_format,
                output_compression=output_compression,
            )
            self._log_usage("generate_image", time.monotonic() - t0, result)

        # Save the image
        image_path = self._save_image(result, output_dir)
        return image_path

    def _save_image(self, result: GenerationResult, output_dir: Path) -> Path:
        """Save a generation result to a file.

        Args:
            result: The generation result containing image data.
            output_dir: Directory to save the image.

        Returns:
            Path to the saved image file.
        """
        # Determine file extension from mime type
        ext = BaseImageProvider.mime_to_extension(result.mime_type)

        # Generate filename with UUID to avoid collisions across threads
        filename = f"generated_{uuid.uuid4().hex[:12]}{ext}"
        image_path = output_dir / filename

        # Use PIL to verify and save the image
        image = Image.open(io.BytesIO(result.image_data))
        image.save(image_path)

        return image_path

    def generate_image_with_references(
        self,
        prompt: ImagePrompt,
        reference_images: list[Path],
        output_dir: Path | str = "output",
        model: str | None = None,
        size: str | None = None,
        aspect_ratio: str | None = None,
        quality: str | None = None,
        temperature: float | None = None,
        output_format: str | None = None,
        output_compression: int | None = None,
    ) -> Path:
        """Generate an image with reference images for identity consistency.

        If ``reference_images`` is empty, delegates to plain text-only
        generation. If references are provided but the current provider does
        not support reference images, raises ``ValueError`` — earlier
        versions silently dropped the references, which produced
        surprisingly off-target output.

        Args:
            prompt: The ImagePrompt containing the full prompt.
            reference_images: Paths to reference sheet images.
            output_dir: Directory to save the generated image.
            model: Model to use (provider-specific).
            size: Size preset or dimensions.
            aspect_ratio: Aspect ratio for the image.
            quality: Quality level (OpenAI only).
            temperature: Generation temperature (lower = more consistent).

        Returns:
            Path to the saved image file.

        Raises:
            ValueError: If reference images are provided but the provider
                does not support them.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        size, aspect_ratio = self._resolve_size(size, aspect_ratio)
        output_format = output_format or self.default_output_format
        if output_compression is None:
            output_compression = self.default_output_compression

        if reference_images and not self.provider.capabilities.supports_reference_images:
            raise ValueError(
                f"Provider '{self.provider_name}' does not support reference "
                "images. Use a provider with supports_reference_images=True "
                "(e.g. 'gemini') or call generate_image() without references."
            )

        t0 = time.monotonic()
        if reference_images:
            result = self.provider.generate_with_references(
                prompt=prompt,
                reference_images=reference_images,
                model=model,
                size=size,
                aspect_ratio=aspect_ratio,
                quality=quality,
                temperature=temperature,
                output_format=output_format,
                output_compression=output_compression,
            )
            method = "generate_image_with_references"
        else:
            result = self.provider.generate(
                prompt=prompt,
                model=model,
                size=size,
                aspect_ratio=aspect_ratio,
                quality=quality,
                output_format=output_format,
                output_compression=output_compression,
            )
            method = "generate_image"
        self._log_usage(method, time.monotonic() - t0, result)

        image_path = self._save_image(result, output_dir)
        return image_path

    def style_transfer_image(
        self,
        input_image: Path | str,
        style: str,
        output_path: Path | str | None = None,
        model: str | None = None,
        size: str | None = None,
        aspect_ratio: str | None = None,
    ) -> Path:
        """Apply a visual style to an existing image.

        Args:
            input_image: Path to the input image file.
            style: Style preset name (e.g. 'anime-dark'), path to a .md file,
                   or raw style prompt text.
            output_path: Where to save the result. If None, auto-generates path.
            model: Model override for the provider.
            size: Size preset (1K, 2K).
            aspect_ratio: Aspect ratio for the output.

        Returns:
            Path to the saved styled image.
        """
        input_image = Path(input_image)
        if not input_image.exists():
            raise FileNotFoundError(f"Input image not found: {input_image}")

        # Resolve style to prompt text
        style_prompt = self._resolve_style(style, self.style_presets_dir)

        # Build the full prompt
        full_prompt = (
            "Apply the following artistic style to this image. "
            "Preserve the subject matter and composition but transform "
            "the visual style completely:\n\n" + style_prompt
        )

        if not self.provider.capabilities.supports_style_transfer:
            raise ValueError(
                f"Provider {self.provider_name} does not support style transfer. "
                "Use 'gemini' provider instead."
            )

        t0 = time.monotonic()
        result = self.provider.style_transfer(
            input_image=input_image,
            style_prompt=full_prompt,
            model=model,
            size=size,
            aspect_ratio=aspect_ratio,
        )
        self._log_usage("style_transfer_image", time.monotonic() - t0, result)

        # Determine output path — default: overwrite in place
        if output_path is None:
            output_path = input_image
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save via PIL
        image = Image.open(io.BytesIO(result.image_data))
        image.save(output_path)

        return output_path

    @staticmethod
    def _resolve_style(style: str, preset_dir: Path | None = None) -> str:
        """Resolve a style argument to prompt text.

        Args:
            style: Style preset name (e.g. 'anime-dark' or 'anime/anime-dark'),
                   file path, or raw style prompt text.
            preset_dir: Directory to search for presets. When None, resolves via
                   ``PIXBRIDGE_STYLE_PRESETS_DIR`` then the default
                   ``prompts/style-transfer``.

        Returns:
            The style prompt text.
        """
        # Check if it's a file path
        style_path = Path(style)
        if style_path.exists() and style_path.is_file():
            return style_path.read_text()

        # Check if it's a preset name (direct path, e.g. "anime/anime-dark")
        preset_dir = _resolve_presets_dir(preset_dir)
        preset_path = preset_dir / f"{style}.md"
        if preset_path.exists():
            return preset_path.read_text()

        # Search subdirectories for bare name (e.g. "anime-dark")
        if preset_dir.exists():
            for md_file in preset_dir.rglob(f"{style}.md"):
                return md_file.read_text()

        # Treat as raw prompt text
        return style

    @staticmethod
    def list_style_presets(preset_dir: Path | None = None) -> list[str]:
        """List available style transfer presets.

        Args:
            preset_dir: Directory to search for presets. When None, resolves via
                   ``PIXBRIDGE_STYLE_PRESETS_DIR`` then the default
                   ``prompts/style-transfer``.

        Returns:
            Sorted list of preset names (including subdirectory prefix,
            e.g. 'anime/anime-dark', 'noir/vintage-editorial-noir').
        """
        preset_dir = _resolve_presets_dir(preset_dir)
        if not preset_dir.exists():
            return []
        return sorted(
            str(p.relative_to(preset_dir).with_suffix(""))
            for p in preset_dir.rglob("*.md")
        )

    @staticmethod
    def available_providers() -> list[str]:
        """List available provider names.

        Returns:
            List of provider names.
        """
        return list_providers()


# Backward compatibility alias
def GeminiImageClient(api_key: str | None = None) -> ImageClient:
    """Create an ImageClient configured for Gemini (backward compatibility).

    Args:
        api_key: Gemini API key. If not provided, reads from
                 GOOGLE_API_KEY or GEMINI_API_KEY environment variables.

    Returns:
        ImageClient instance configured for Gemini provider.
    """
    return ImageClient(provider="gemini", api_key=api_key)


# Keep the old constants for backward compatibility
VALID_SIZES = ["1K", "2K"]
VALID_ASPECT_RATIOS = ["16:9", "4:3", "3:4", "9:16", "1:1"]
