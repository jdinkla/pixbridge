# CLAUDE.md

## Project Purpose

Standalone multi-provider AI image generation library. Supports Gemini, OpenAI, and xAI providers through a unified `ImageClient` API.

## Project Structure

```
src/pixbridge/
  __init__.py
  _usage_log.py          # Thread-safe JSONL usage logging (inlined)
  client.py              # ImageClient — unified generation API
  cli.py                 # CLI entry point (pixbridge command)
  config.py              # YAML loader for model_config.yaml
  models.py              # Pydantic models (ImagePrompt, GenerationNotes)
  size_resolver.py       # Resolves preset/WxH sizes to provider-native sizes
  integrity_check.py     # Image integrity validation
  consistency_check.py   # Multi-image consistency testing
  providers/
    __init__.py           # Provider registry (get_provider, list_providers)
    base.py               # BaseImageProvider ABC, GenerationResult, ProviderCapabilities
    gemini.py
    openai.py
    xai.py
    vertex.py
model_config.yaml         # Per-provider default model (auto-discovered from cwd)
tests/pixbridge/          # Unit tests (no __init__.py — avoids shadowing the package)
```

## Development

```bash
uv sync              # Install dependencies
just test            # Run tests
just build           # Alias for uv sync
```

## Style Presets

`client.py` resolves style presets via `Path("prompts/style-transfer")` relative to cwd. When no preset directory exists, styles are treated as raw prompt text.

## Key Design Decisions

- `_usage_log.py` is inlined from the original `common.usage_log` module to avoid external dependencies
- Provider instances are lazily initialized (no API key needed until first generation call)
- Tests do not have an `__init__.py` in `tests/pixbridge/` to prevent namespace shadowing with the installed package
- Model selection uses a flat `model_config.yaml` schema (`providers.<name>.default_model`). By default any model string flows through to the provider SDK — a provider only restricts models if its `ProviderCapabilities.supported_models` is a non-empty allowlist (OpenAI: `gpt-image-2`). When it is, `validate_params` rejects unknown models locally with a `ValueError` before any API call; otherwise (Gemini/xAI/vertex, `supported_models=None`) unknown models pass through and SDK-rejected combinations surface as runtime SDK errors.
- OpenAI support targets `gpt-image-2` only (older `gpt-image-1.x` models are no longer supported; the `supported_models` allowlist enforces this). Its capability `sizes` list (`1024x1024`, `1024x1536`, `1536x1024`, `2560x1440`, `3840x2160`) is a set of recommended values for docs/autocompletion; actual validation is rule-based via `validate_openai_size` (both dims divisible by 16, ratio in `[1:3, 3:1]`, `max(W, H) ≤ 3840`).
- OpenAI style transfer and reference images run through `client.images.edit` (single reference = style transfer, multiple = composition). gpt-image-2 has no dedicated "style" parameter — both capabilities are delivered via the edits endpoint.
