# Changelog

All notable changes to pixbridge are documented in this file.

## [Unreleased]

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
