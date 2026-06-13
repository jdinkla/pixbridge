"""Command-line interface for image generation."""

import argparse
import sys
from pathlib import Path

import yaml

from .client import ImageClient, _resolve_presets_dir
from .config import get_configured_model, load_model_config
from .consistency_check import (
    DEFAULT_COUNT,
    DEFAULT_TEST_SCENE,
    ConsistencyResult,
    normalize_style_label,
    run_consistency_check,
)
from .integrity_check import check_directory, check_image
from .models import ImagePrompt
from .providers import get_provider, list_providers
from .size_resolver import resolve_size_preset

DEFAULT_USAGE_LOG = Path("usage.jsonl")


def load_prompt_from_yaml(yaml_path: Path) -> ImagePrompt:
    """Load an ImagePrompt from a YAML file.

    Args:
        yaml_path: Path to the YAML file containing the prompt.

    Returns:
        Parsed ImagePrompt object.
    """
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    # Handle nested structure (image_prompt key) or flat structure
    if "image_prompt" in data:
        prompt_data = data["image_prompt"]
    else:
        prompt_data = data

    return ImagePrompt.model_validate(prompt_data)


DEFAULT_CONFIG = Path("model_config.yaml")


def _load_config_from_args(args: argparse.Namespace) -> dict | None:
    """Load model config: explicit --config path, or auto-discover model_config.yaml in cwd.

    Returns:
        Parsed config dict, or None if no config file found.

    Raises:
        SystemExit: If an explicit --config path is not found or invalid.
    """
    config_path = getattr(args, "config", None)
    if config_path is not None:
        # Explicit path — error if missing/invalid
        try:
            return load_model_config(Path(config_path))
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Auto-discover in cwd — silently skip if absent
    if DEFAULT_CONFIG.exists():
        try:
            return load_model_config(DEFAULT_CONFIG)
        except (FileNotFoundError, ValueError):
            return None

    return None


def generate_command(args: argparse.Namespace) -> int:
    """Handle the generate command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    yaml_path = Path(args.prompt_file)
    if not yaml_path.exists():
        print(f"Error: File not found: {yaml_path}", file=sys.stderr)
        return 1

    output_dir = Path(args.output) if args.output else Path("output")

    try:
        # Load the prompt
        print(f"Loading prompt from {yaml_path}...")
        prompt = load_prompt_from_yaml(yaml_path)

        # Initialize client with selected provider
        provider_name = args.provider
        print(f"Initializing {provider_name} client...")
        client = ImageClient(provider=provider_name, usage_log=DEFAULT_USAGE_LOG)

        # Get provider capabilities for defaults
        caps = client.provider.capabilities

        # Resolve model: CLI flag > config file > provider default
        config = _load_config_from_args(args)
        config_model = get_configured_model(config, provider_name)

        # Resolve size presets (720p, 1080p, 2160p) — only when user provided --size
        resolved_size: str | None
        preset_aspect: str | None
        if args.size is not None:
            resolved_size, preset_aspect = resolve_size_preset(args.size, provider_name)
        else:
            resolved_size = None
            preset_aspect = None

        # aspect_ratio resolution: CLI flag > size-preset aspect > YAML prompt
        aspect_ratio = (
            args.aspect_ratio
            or preset_aspect
            or prompt.generation_notes.aspect_ratio
        )

        # Build generation parameters
        model = args.model or config_model or caps.default_model
        gen_params: dict[str, str | None] = {
            "model": model,
            "aspect_ratio": aspect_ratio,
        }

        # Forward size to providers that use it; forward quality to openai.
        if provider_name in ("gemini", "openai") and resolved_size is not None:
            gen_params["size"] = resolved_size
        if provider_name == "openai":
            gen_params["quality"] = args.quality or caps.default_quality

        print(f"Generating image with provider {provider_name}...")
        print(f"  Model: {model}")
        print(f"  Aspect ratio: {aspect_ratio}")
        if "size" in gen_params:
            print(f"  Size: {gen_params['size']}")
        if provider_name == "openai":
            print(f"  Quality: {gen_params['quality']}")

        image_path = client.generate_image(
            prompt,
            output_dir,
            model=model,
            aspect_ratio=aspect_ratio,
            size=gen_params.get("size"),
            quality=gen_params.get("quality"),
        )

        print(f"Image saved to: {image_path}")
        return 0

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error generating image: {e}", file=sys.stderr)
        return 1


def providers_command(args: argparse.Namespace) -> int:
    """Handle the providers command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    providers = list_providers()
    print("Available providers:")
    print()

    for name in providers:
        try:
            # Create provider instance to get capabilities
            # Note: This won't fail even without API key since we're just reading capabilities
            provider = get_provider(name)
            caps = provider.capabilities

            print(f"  {name}:")
            print(f"    Default model: {caps.default_model or 'N/A'}")
            if caps.sizes:
                print(f"    Sizes: {', '.join(caps.sizes)}")
            print(f"    Aspect ratios: {', '.join(caps.aspect_ratios)}")
            if caps.quality_levels:
                print(f"    Quality levels: {', '.join(caps.quality_levels)}")
            print()
        except Exception as e:
            print(f"  {name}: (error loading capabilities: {e})")
            print()

    return 0


def style_transfer_command(args: argparse.Namespace) -> int:
    """Handle the style-transfer command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    # Handle --list-styles
    styles_dir = Path(args.styles_dir) if args.styles_dir else None
    if args.list_styles:
        presets = ImageClient.list_style_presets(styles_dir)
        if not presets:
            search_dir = _resolve_presets_dir(styles_dir)
            print(f"No style presets found in {search_dir}/")
            return 0
        print("Available style presets:")
        for name in presets:
            print(f"  {name}")
        return 0

    # Validate required args when not listing
    if not args.input:
        print("Error: input image or directory is required", file=sys.stderr)
        return 1

    if not args.style:
        print("Error: --style is required", file=sys.stderr)
        return 1

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input not found: {input_path}", file=sys.stderr)
        return 1

    try:
        client = ImageClient(
            provider="gemini", usage_log=DEFAULT_USAGE_LOG, style_presets_dir=styles_dir
        )

        # Resolve model: CLI flag > config file > None (let provider decide)
        config = _load_config_from_args(args)
        config_model = get_configured_model(config, "gemini")
        resolved_model = args.model or config_model
        args.model = resolved_model

        # Batch mode
        if args.batch:
            if not input_path.is_dir():
                print(f"Error: --batch requires a directory, got: {input_path}", file=sys.stderr)
                return 1
            return _batch_style_transfer(client, input_path, args)

        # Single file mode
        if not input_path.is_file():
            print(f"Error: Input is not a file: {input_path}", file=sys.stderr)
            return 1

        output_path = Path(args.output) if args.output else None
        print(f"Applying style '{args.style}' to {input_path}...")

        result_path = client.style_transfer_image(
            input_image=input_path,
            style=args.style,
            output_path=output_path,
            model=resolved_model,
            size=args.size,
            aspect_ratio=args.aspect_ratio,
        )
        print(f"Styled image saved to: {result_path}")
        return 0

    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error during style transfer: {e}", file=sys.stderr)
        return 1


def _batch_style_transfer(
    client: ImageClient, input_dir: Path, args: argparse.Namespace
) -> int:
    """Process all images in a directory for style transfer.

    Args:
        client: ImageClient instance.
        input_dir: Directory containing input images.
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    output_dir = Path(args.output) if args.output else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(
        p for p in input_dir.iterdir()
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )

    if not images:
        print(f"No images found in {input_dir}")
        return 0

    dest = output_dir or input_dir
    print(f"Processing {len(images)} images with style '{args.style}'...")
    success = 0
    for i, img in enumerate(images, 1):
        out_path = (output_dir / img.name) if output_dir else None
        print(f"  [{i}/{len(images)}] {img.name}...", end=" ", flush=True)
        try:
            client.style_transfer_image(
                input_image=img,
                style=args.style,
                output_path=out_path,
                model=args.model,
                size=args.size,
                aspect_ratio=args.aspect_ratio,
            )
            print("done")
            success += 1
        except Exception as e:
            print(f"failed: {e}")

    print(f"\nCompleted: {success}/{len(images)} images styled in {dest}")
    return 0


def consistency_check_command(args: argparse.Namespace) -> int:
    """Handle the consistency-check command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success/partial success, 1 for total failure).
    """
    try:
        # Resolve style text and normalize label for filenames/dirs
        styles_dir = Path(args.styles_dir) if args.styles_dir else None
        style_text = ImageClient._resolve_style(args.style, styles_dir)
        style_label = normalize_style_label(args.style)

        provider_name = args.provider
        provider = get_provider(provider_name)
        caps = provider.capabilities

        # Resolve model: CLI flag > config file > provider default
        config = _load_config_from_args(args)
        config_model = get_configured_model(config, provider_name)
        model = args.model or config_model or caps.default_model

        # Resolve size presets (720p, 1080p, 2160p)
        resolved_size, preset_aspect = resolve_size_preset(args.size, provider_name)
        aspect_ratio = preset_aspect if preset_aspect else args.aspect_ratio

        # Build provider-specific params
        gen_params: dict = {}
        if model:
            gen_params["model"] = model
        if aspect_ratio:
            gen_params["aspect_ratio"] = aspect_ratio
        if provider_name == "gemini" and resolved_size:
            gen_params["size"] = resolved_size
        elif provider_name == "openai":
            gen_params["quality"] = args.quality or caps.default_quality

        output_dir = (
            Path(args.output)
            if args.output
            else Path(f"generated/consistency-check/{style_label}_{provider_name}")
        )

        scene = args.scene if args.scene else DEFAULT_TEST_SCENE
        count = args.count

        print(f"Running consistency check for style '{style_label}'")
        print(f"  Provider: {provider_name}")
        print(f"  Model: {model}")
        print(f"  Count: {count}")
        print(f"  Output: {output_dir}")

        result: ConsistencyResult = run_consistency_check(
            provider=provider,
            style=style_label,
            style_text=style_text,
            output_dir=output_dir,
            count=count,
            scene=scene,
            **gen_params,
        )

        print(f"\nCompleted in {result.duration_s}s")
        print(f"  Generated: {len(result.images)}/{result.count}")
        for img in result.images:
            print(f"    {img}")
        if result.failures:
            print(f"  Failures: {len(result.failures)}")
            for fail in result.failures:
                print(f"    {fail}")

        # Total failure = exit 1, partial success = exit 0
        if not result.images:
            return 1
        return 0

    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error during consistency check: {e}", file=sys.stderr)
        return 1


def check_command(args: argparse.Namespace) -> int:
    """Handle the check command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 = all ok, 1 = issues found).
    """
    path = Path(args.path)
    if not path.exists():
        print(f"Error: Path not found: {path}", file=sys.stderr)
        return 1

    threshold = args.threshold

    if path.is_file():
        result = check_image(path, transparency_threshold=threshold)
        print(result.summary())
        return 0 if result.ok else 1

    if not path.is_dir():
        print(f"Error: Not a file or directory: {path}", file=sys.stderr)
        return 1

    results = check_directory(path, transparency_threshold=threshold)
    if not results:
        print(f"No images found in {path}")
        return 0

    failures = [r for r in results if not r.ok]
    for r in failures:
        print(r.summary())

    print(f"\n{len(results)} images checked, {len(failures)} failed")
    return 1 if failures else 0


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="pixbridge",
        description="Generate images from prompts using multiple AI providers",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to model_config.yaml for provider model defaults",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Generate command
    gen_parser = subparsers.add_parser(
        "generate", help="Generate an image from a YAML prompt file"
    )
    gen_parser.add_argument(
        "prompt_file", type=str, help="Path to YAML file containing the image prompt"
    )
    gen_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output directory for generated images (default: ./output/)",
    )
    gen_parser.add_argument(
        "--provider",
        "-p",
        type=str,
        choices=list_providers(),
        default="gemini",
        help="Image generation provider (default: gemini)",
    )
    gen_parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Model to use (provider-specific, uses default if not specified)",
    )
    gen_parser.add_argument(
        "--size",
        "-s",
        type=str,
        default=None,
        help="Size: 720p/1080p/2160p preset, WxH (e.g. 1920x1080), or provider-specific (Gemini: 1K/2K, OpenAI: 1024x1024/1536x1024/2560x1440/3840x2160). Default: provider default.",
    )
    gen_parser.add_argument(
        "--aspect-ratio",
        "-a",
        type=str,
        choices=["16:9", "4:3", "3:4", "9:16", "1:1"],
        default=None,
        help="Aspect ratio. If omitted, uses the prompt YAML's generation_notes.aspect_ratio, then a size-preset aspect if --size implies one. Note: xAI does not support 3:4 or 9:16.",
    )
    gen_parser.add_argument(
        "--quality",
        "-q",
        type=str,
        choices=["low", "medium", "high"],
        default=None,
        help="Quality level for OpenAI provider (default: provider default, currently 'low' for gpt-image-2)",
    )

    # Style-transfer command
    st_parser = subparsers.add_parser(
        "style-transfer", help="Apply a visual style to an existing image"
    )
    st_parser.add_argument(
        "input",
        type=str,
        nargs="?",
        default=None,
        help="Input image path (or directory with --batch)",
    )
    st_parser.add_argument(
        "--style",
        "-s",
        type=str,
        default=None,
        help="Style preset name (e.g. anime-dark) or path to .md style file",
    )
    st_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path (or directory with --batch)",
    )
    st_parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Model override (default: gemini-3-pro-image-preview)",
    )
    st_parser.add_argument(
        "--size",
        type=str,
        default=None,
        choices=["1K", "2K"],
        help="Output size preset (default: provider default 1K)",
    )
    st_parser.add_argument(
        "--aspect-ratio",
        "-a",
        type=str,
        choices=["16:9", "4:3", "3:4", "9:16", "1:1"],
        default=None,
        help="Aspect ratio (default: preserve provider default)",
    )
    st_parser.add_argument(
        "--list-styles",
        action="store_true",
        help="List available style presets and exit",
    )
    st_parser.add_argument(
        "--styles-dir",
        type=str,
        default=None,
        help="Directory of style preset .md files "
        "(default: $PIXBRIDGE_STYLE_PRESETS_DIR or prompts/style-transfer)",
    )
    st_parser.add_argument(
        "--batch",
        "-b",
        action="store_true",
        help="Process all images in the input directory",
    )

    # Consistency-check command
    cc_parser = subparsers.add_parser(
        "consistency-check",
        help="Generate N images from the same style+scene for visual comparison",
    )
    cc_parser.add_argument(
        "style",
        type=str,
        help="Style preset name (e.g. anime-dark) or path to .md style file",
    )
    cc_parser.add_argument(
        "--provider",
        "-p",
        type=str,
        choices=list_providers(),
        default="gemini",
        help="Image generation provider (default: gemini)",
    )
    cc_parser.add_argument(
        "--count",
        "-n",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Number of images to generate (default: {DEFAULT_COUNT})",
    )
    cc_parser.add_argument(
        "--styles-dir",
        type=str,
        default=None,
        help="Directory of style preset .md files "
        "(default: $PIXBRIDGE_STYLE_PRESETS_DIR or prompts/style-transfer)",
    )
    cc_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output directory (default: output/consistency-check/{style}_{provider}/)",
    )
    cc_parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Model to use (provider-specific, uses default if not specified)",
    )
    cc_parser.add_argument(
        "--size",
        "-s",
        type=str,
        default="1K",
        help="Size: 720p/1080p/2160p preset, WxH (e.g. 1920x1080), or provider-specific (Gemini: 1K/2K, OpenAI: 1024x1024/etc). Default: 1K.",
    )
    cc_parser.add_argument(
        "--aspect-ratio",
        "-a",
        type=str,
        choices=["16:9", "4:3", "3:4", "9:16", "1:1"],
        default="16:9",
        help="Aspect ratio (default: 16:9)",
    )
    cc_parser.add_argument(
        "--quality",
        "-q",
        type=str,
        choices=["low", "medium", "high"],
        default=None,
        help="Quality level for OpenAI provider",
    )
    cc_parser.add_argument(
        "--scene",
        type=str,
        default=None,
        help="Override the default test scene description",
    )

    # Check command
    check_parser = subparsers.add_parser(
        "check",
        help="Check images for integrity issues (transparency, corruption, truncation)",
    )
    check_parser.add_argument(
        "path",
        type=str,
        help="Image file or directory to check",
    )
    check_parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=0.01,
        help="Transparency threshold (fraction of non-opaque pixels, default: 0.01)",
    )

    # Providers command
    subparsers.add_parser(
        "providers", help="List available image generation providers"
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "generate":
        return generate_command(args)

    if args.command == "style-transfer":
        return style_transfer_command(args)

    if args.command == "consistency-check":
        return consistency_check_command(args)

    if args.command == "check":
        return check_command(args)

    if args.command == "providers":
        return providers_command(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
