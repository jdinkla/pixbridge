# Changelog

All notable changes to pixbridge are documented in this file.

## [0.2.1] - 2026-06-18

### Fixed — style can no longer hijack the consistency-check scene

- `build_consistency_prompt` now states the scene imperatively (`Depict
  exactly this scene: ...`) and wraps the style block with an explicit scope
  clause: the style governs only the look (medium, palette, lighting, texture,
  composition), not the subject or action, which are set by the scene. A
  trailing reminder reinforces it for recency.
- Without this, a long or subject-heavy style preset could outweigh a short
  scene description and override it (e.g. a photoreal-prehistoric preset
  rendered a mammoth hunt over a neutral test scene). Scene and style text are
  still both present verbatim — this only reframes, never drops, either input.

## [0.2.0] - 2026-06-13

### Changed (breaking) — a model must always be specified

- There is no longer any default model. Every generation requires an explicit
  model:
  - **CLI:** `--model` is required on `generate`, `style-transfer`, and
    `consistency-check`. Omitting it prints `--model is required` and exits 1.
  - **Library:** pass `model=` to the `ImageClient` generation methods; omitting
    it raises `ValueError` (enforced centrally in
    `BaseImageProvider.validate_params`).
- Rationale: model names churn, so the library no longer ships a baked-in
  default that could silently go stale.

### Removed (breaking)

- `ProviderCapabilities.default_model` — the hardcoded per-provider default.
- `model_config.yaml`, the `config.py` loader (`load_model_config`,
  `get_configured_model`), and the `--config` / `-c` CLI flag. Provider model
  defaults are no longer read from a config file.

Migration: replace reliance on the default/config with an explicit
`--model <name>` (CLI) or `model="<name>"` (library) on every call.

## [0.1.1] - 2026-06-13

### Added — configurable style-preset directory

- `ImageClient(style_presets_dir=...)` lets callers point style-transfer preset
  lookup at any directory instead of the cwd-relative `prompts/style-transfer`.
- New `PIXBRIDGE_STYLE_PRESETS_DIR` environment variable overrides the default
  directory globally; the `style-transfer` and `consistency-check` CLI commands
  gain a `--styles-dir` flag. Resolution order: explicit argument →
  environment variable → `prompts/style-transfer`.
- `_resolve_style()` and `list_style_presets()` accept an optional `preset_dir`.

This removes the prior hard dependency on running from a directory that happened
to contain `prompts/style-transfer`.

## [0.1.0] - 2026-06-13

First open-source release (renamed from the internal `image-genpy` package).

### Changed (breaking) — OpenAI size handling

- **`--aspect-ratio 9:16` now resolves to `1152x2048`** (was `1024x1536`, which is
  actually 2:3). Callers wanting the previous behavior should pass
  `--aspect-ratio 2:3` or an explicit `--size 1024x1536`.
- **`--aspect-ratio 16:9` now resolves to `2048x1152`** (was `1536x1024`, which is
  actually 3:2). Callers wanting the previous behavior should pass
  `--aspect-ratio 3:2` or an explicit `--size 1536x1024`.
- Cost impact for callers consuming the new defaults: roughly 50% more pixels,
  ~50% higher token cost (e.g. ~$0.005 → ~$0.008 per low-quality 9:16 image).

### Changed — OpenAI size validation is now rule-based

- `OpenAIProvider.validate_params` no longer checks `size` against a hardcoded
  five-element allowlist. Any WxH meeting gpt-image-2's actual rules is
  accepted:
  - both dimensions divisible by 16,
  - aspect ratio in `[1:3, 3:1]`,
  - `max(W, H) ≤ 3840`.
- `ProviderCapabilities.sizes` for OpenAI now lists *recommended* sizes (for
  docs/autocompletion); validation accepts any rule-conformant size beyond the
  list.
- `size_resolver._resolve_wxh` for the OpenAI provider no longer silently snaps
  invalid sizes to the nearest allowed one. Invalid sizes now raise
  `ValueError`. The silent-snap behavior had been masking a bug where
  `1080x1920` (and other 9:16-ish but non-/16 dimensions) was downgraded to
  `1024x1536` (which is actually 2:3).

### Added

- `pixbridge.providers.openai.validate_openai_size(size)` and
  `is_valid_openai_size(size)` helpers exposed at the module level.
- Explicit `"3:2"` and `"2:3"` aspect-ratio aliases for the legacy
  `1536x1024` / `1024x1536` mappings.
- True 9:16 (`1152x2048`) and 16:9 (`2048x1152`) recommended sizes in
  `OpenAIProvider.capabilities.sizes`.
