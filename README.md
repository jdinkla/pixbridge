# pixbridge

[![CI](https://github.com/jdinkla/pixbridge/actions/workflows/ci.yml/badge.svg)](https://github.com/jdinkla/pixbridge/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

Multi-provider AI image generation library supporting Gemini, OpenAI, and xAI.

## Features

- Unified `ImageClient` API across providers
- Image generation from structured YAML prompts
- Style transfer (Gemini)
- Reference image support for identity consistency (Gemini)
- Consistency checking (generate N images from the same prompt for comparison)
- Image integrity checks (transparency, corruption, truncation)
- Thread-safe usage logging (JSONL)

## Setup

```bash
uv sync
```

## CLI

```bash
pixbridge providers                          # List available providers
pixbridge generate prompt.yaml               # Generate from YAML prompt
pixbridge style-transfer img.png --style anime-dark
pixbridge consistency-check anime-dark -n 5
pixbridge check output/                      # Check image integrity
```

## Usage as library

```python
from pixbridge.client import ImageClient
from pixbridge.models import ImagePrompt, GenerationNotes

client = ImageClient(provider="gemini")
prompt = ImagePrompt(
    full_prompt="A mountain landscape at sunset",
    generation_notes=GenerationNotes(
        aspect_ratio="16:9",
        key_requirements=["photorealistic"],
    ),
)
path = client.generate_image(prompt, output_dir="output")
```

## Providers

| Provider | Models | Style Transfer | Reference Images |
|----------|--------|:-:|:-:|
| Gemini | gemini-3-pro-image-preview | yes | yes |
| OpenAI | gpt-image-2 (default), gpt-image-1.5, gpt-image-1, gpt-image-1-mini | no | no |
| xAI | grok-imagine-image | no | no |

Any model can be selected at runtime with `--model`. The CLI also accepts size presets `720p`, `1080p`, `2160p`, or a raw `WxH` string (resolved per-provider). OpenAI (`gpt-image-2`) validates sizes by rule — any `WxH` where both dimensions are divisible by 16, the ratio is within `[1:3, 3:1]`, and `max(W, H) ≤ 3840` — so true `9:16` (`1152x2048`) and `16:9` (`2048x1152`) work; `1024x1024`, `1024x1536`, `1536x1024`, `2560x1440`, `3840x2160` are recommended values surfaced for autocompletion.

### Provider capability surface

Each provider exposes a uniform capability surface via `provider.capabilities` (a `ProviderCapabilities`), so callers can reason about size rules without branching on the provider name:

| Method | Returns | OpenAI | Gemini / Vertex | xAI |
|--------|---------|--------|-----------------|-----|
| `validate_size(size)` | raises `ValueError` if invalid | rule-based (÷16, ratio, max-dim) | must be `1K`/`2K` | no-op (unconstrained) |
| `recommended_sizes()` | `list[str]` for docs/autocomplete | 7 sizes incl. true 9:16/16:9 | `["1K", "2K"]` | `[]` |
| `aspect_to_size(ratio)` | `str \| None` (named ratio → `WxH`) | e.g. `"9:16" → "1152x2048"` | `None` (ratio passed to API) | `None` |
| `max_dim()` | `int \| None` (px ceiling) | `3840` | `None` | `None` |
| `native_size(w, h)` | `str \| None` (raw `WxH` → native size) | validates + passes `WxH` through | buckets to `1K`/`2K` | `None` |

To read a provider's capabilities **without instantiating it or supplying credentials** (e.g. for offline size resolution), use the registry:

```python
from pixbridge.providers import get_capabilities

caps = get_capabilities("openai")   # also "gemini", "xai", "vertex"; None if unknown
caps.validate_size("1152x2048")     # passes; raises ValueError on invalid sizes
caps.native_size(2048, 1152)        # -> "2048x1152"
```

`get_capabilities("vertex")` returns Gemini's surface (Vertex shares it) and never requires `GOOGLE_CLOUD_PROJECT`.

## Style presets

Style-transfer presets are Markdown files looked up by name. Pass `--style` (or
the `style` argument) as a preset name (`anime-dark`), a subdir-qualified name
(`anime/anime-dark`), a path to a `.md` file, or raw prompt text.

The preset directory resolves in this order: an explicit
`ImageClient(style_presets_dir=...)` / `--styles-dir` argument, then the
`PIXBRIDGE_STYLE_PRESETS_DIR` environment variable, then `prompts/style-transfer`
relative to the current working directory. When none of these contain the named
preset, the value is treated as raw prompt text.

```bash
export PIXBRIDGE_STYLE_PRESETS_DIR=~/my-styles
pixbridge style-transfer img.png --style anime-dark
pixbridge style-transfer img.png --style anime-dark --styles-dir ./other-styles
```

```python
client = ImageClient(provider="gemini", style_presets_dir="~/my-styles")
```

## Configuration

Per-provider defaults live in `model_config.yaml` (auto-discovered from the current working directory, or pass `--config path/to/file.yaml`). Resolution order: `--model` CLI flag > config file > hardcoded provider default.

```yaml
providers:
  openai:
    default_model: gpt-image-2
  gemini:
    default_model: gemini-3.1-flash-image-preview
```

## Testing

```bash
just test
```

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for the
development setup and PR guidelines. To report a security issue, see
[SECURITY.md](SECURITY.md).

## License

Licensed under the [Apache License 2.0](LICENSE). See the [NOTICE](NOTICE) file
for attribution requirements.
