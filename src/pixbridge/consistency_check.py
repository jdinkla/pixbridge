"""Style transfer prompt consistency check — generate N images from the same
style prompt + test scene to visually compare consistency across generations."""

import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from .models import GenerationNotes, ImagePrompt
from .providers.base import BaseImageProvider

DEFAULT_TEST_SCENE = (
    "A person sitting at a wooden desk in a dimly lit room. "
    "A warm desk lamp casts directional light across scattered papers "
    "and an open notebook. Floor-to-ceiling bookshelves line the back wall. "
    "A ceramic coffee cup sits near the edge of the desk."
)

DEFAULT_COUNT = 5


def normalize_style_label(style: str) -> str:
    """Extract a clean label from a style argument for use in filenames/dirs.

    Handles preset names ('anime-dark' or 'anime/anime-dark'), file paths
    ('prompts/style-transfer/anime/anime-dark.md'), and raw text (returned
    as-is but truncated).
    """
    p = Path(style)
    if "/" in style or style.endswith(".md"):
        return p.stem
    return style


@dataclass
class ConsistencyResult:
    """Result of a consistency check run."""

    style: str
    provider: str
    count: int
    images: list[Path] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    duration_s: float = 0.0


def build_consistency_prompt(scene: str, style_text: str) -> ImagePrompt:
    """Combine a test scene with style text into an ImagePrompt.

    The scene is stated imperatively and the style block is explicitly scoped to
    "look only", so a long or subject-heavy style preset cannot hijack the scene's
    subject and action. Without this framing, a verbose style (e.g. one that
    repeatedly names creatures or actions) outweighs a short scene and overrides it.

    Args:
        scene: Scene description.
        style_text: Style prompt text (from preset or file).

    Returns:
        ImagePrompt ready for generation.
    """
    full_prompt = (
        f"Depict exactly this scene: {scene}\n\n"
        "Render it in the following visual style. The style governs only the look "
        "— medium, palette, lighting, texture, and composition — not the subject "
        "or action, which are set by the scene above:\n"
        f"{style_text}\n\n"
        "Keep the subject and action of the scene; apply the style only to how it looks."
    )
    return ImagePrompt(
        full_prompt=full_prompt,
        generation_notes=GenerationNotes(
            aspect_ratio="16:9",
            key_requirements=[
                "consistent style across multiple generations",
                "character rendering",
                "directional lighting",
                "environment depth",
            ],
        ),
    )


def run_consistency_check(
    provider: BaseImageProvider,
    style: str,
    style_text: str,
    output_dir: Path,
    count: int = DEFAULT_COUNT,
    scene: str = DEFAULT_TEST_SCENE,
    model: str | None = None,
    size: str | None = None,
    aspect_ratio: str | None = None,
    quality: str | None = None,
) -> ConsistencyResult:
    """Generate N images from the same style+scene for visual comparison.

    Args:
        provider: Initialized image provider instance.
        style: Style name (used for filenames).
        style_text: Style prompt text.
        output_dir: Directory to save generated images.
        count: Number of images to generate.
        scene: Test scene description.
        model: Model override.
        size: Size override (Gemini).
        aspect_ratio: Aspect ratio override.
        quality: Quality override (OpenAI).

    Returns:
        ConsistencyResult with paths to generated images and any failures.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_consistency_prompt(scene, style_text)
    provider_name = provider.name

    # Force lazy init before threading (avoid race on first API call)
    _ = provider.capabilities

    result = ConsistencyResult(
        style=style,
        provider=provider_name,
        count=count,
    )

    gen_kwargs: dict = {"prompt": prompt, "model": model, "aspect_ratio": aspect_ratio}
    if size is not None:
        gen_kwargs["size"] = size
    if quality is not None:
        gen_kwargs["quality"] = quality

    t0 = time.monotonic()

    def _generate_one(index: int) -> tuple[int, Path | None, str | None]:
        """Generate a single image. Returns (index, path_or_none, error_or_none)."""
        try:
            gen_result = provider.generate(**gen_kwargs)
            ext = BaseImageProvider.mime_to_extension(gen_result.mime_type)
            filename = f"{style}_{provider_name}_{index:02d}{ext}"
            image_path = output_dir / filename
            image = Image.open(io.BytesIO(gen_result.image_data))
            image.save(image_path)
            return (index, image_path, None)
        except Exception as e:
            return (index, None, str(e))

    max_workers = min(count, 5)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_generate_one, i): i for i in range(1, count + 1)}
        for future in as_completed(futures):
            idx, path, error = future.result()
            if path is not None:
                result.images.append(path)
            else:
                result.failures.append(f"Image {idx:02d}: {error}")

    result.images.sort()
    result.duration_s = round(time.monotonic() - t0, 3)
    return result
