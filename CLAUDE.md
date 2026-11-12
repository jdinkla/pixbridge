# CLAUDE.md

## Project Purpose

Standalone multi-provider AI image generation library. Supports Gemini, OpenAI, xAI, and Vertex AI providers through a unified `ImageClient` API.

## Development

```bash
uv sync              # Install dependencies
just test            # Run tests
just build           # Alias for uv sync
```

## Style Presets

`client.py` finds the style-preset directory in this order: `ImageClient(style_presets_dir=...)`, the `PIXBRIDGE_STYLE_PRESETS_DIR` environment variable, then `prompts/style-transfer` relative to cwd. A style argument is tried as a file path, then as a preset name in that directory; if neither matches it is treated as raw prompt text.

## Key Design Decisions

- `_usage_log.py` is deliberately self-contained so usage logging needs no external dependency
- Provider instances are lazily initialized (no API key needed until first generation call)
- Tests do not have an `__init__.py` in `tests/pixbridge/` to prevent namespace shadowing with the installed package
- There is no default model and no config file (one known exception: Gemini style transfer still falls back to `GeminiProvider.STYLE_TRANSFER_MODEL`; removing it is TASK-5). A model must always be specified explicitly — `--model` on the CLI (required on `generate`/`style-transfer`/`consistency-check`; commands print `--model is required` and exit 1 otherwise) or `model=` on the `ImageClient` methods. Enforcement is centralized in `BaseImageProvider.validate_params`, which raises `ValueError` when `model is None`. This is deliberate: model names churn, so no baked-in default is allowed to go stale. By default any model string flows through to the provider SDK — a provider only restricts models if its `ProviderCapabilities.supported_models` is a non-empty allowlist (OpenAI: `gpt-image-2`, GPT Image 2.5 and 2.6 Flare/Sunburst aliases and the published 2.5 snapshots). When it is, `validate_params` rejects unknown models locally with a `ValueError` before any API call; otherwise (Gemini/xAI/vertex, `supported_models=None`) unknown models pass through and SDK-rejected combinations surface as runtime SDK errors.
- OpenAI supports `gpt-image-2`, `gpt-image-2.5-flare`, `gpt-image-2.5-sunburst`, `gpt-image-2.6-flare`, and `gpt-image-2.6-sunburst` (including the 2.5 `-2026-09-08` snapshots; 2.6 has none yet). Only 2.5 and 2.6 accept `xhigh` and `max`; all accept `low`, `medium`, `high`, and `auto` (verified live for 2.6 on 2026-11-12). Only 2.6 accepts `complexity` (`low`/`medium`/`high`, `ProviderCapabilities.complexity_levels`); it is sent via `extra_body` because older SDKs have no named parameter, is omitted from the request when not set, and `ImageClient` passes it to a provider only when set so other providers keep their signatures. OpenAI support targets these families only (older `gpt-image-1.x` models are no longer supported; the `supported_models` allowlist enforces this). Its capability `sizes` list (`1024x1024`, `1024x1536`, `1536x1024`, `1152x2048`, `2048x1152`, `2560x1440`, `3840x2160`) is a set of recommended values for docs/autocompletion; actual validation is rule-based via `validate_openai_size` (both dims divisible by 16, ratio in `[1:3, 3:1]`, `max(W, H) ≤ 3840`, total pixels in `[655360, 8294400]`).
- OpenAI style transfer and reference images run through `client.images.edit` (single reference = style transfer, multiple = composition). gpt-image-2 has no dedicated "style" parameter — both capabilities are delivered via the edits endpoint.

## Working Autonomously

These override the Backlog.md guides below where they conflict.

- Create Backlog tasks for follow-up work you discover, without asking. This overrides the finalization guide's "Do not create or start follow-up tasks without user approval" for *creating* tasks. Starting a follow-up task still needs a go-ahead.
- Commit finished, verified work without asking. Do not push without being asked.

<!-- BACKLOG.MD GUIDELINES START -->
<!-- backlog.md-instructions-version: 1.55.3 -->
## Backlog.md Workflow

This project uses Backlog.md for task and project management.

At the beginning of each conversation in this project, run `backlog instructions overview` before answering or taking action. Re-read it only if you have not read it yet in the current conversation.

Use the overview to decide whether to search, read, create, or update Backlog tasks.

Before task lifecycle actions, read the matching detailed guide:
- `backlog instructions task-creation` before creating or splitting tasks
- `backlog instructions task-execution` before planning, changing status or assignee, adding a plan or implementation notes, or implementing task work
- `backlog instructions task-finalization` before checking acceptance criteria, writing final summaries, or moving tasks to terminal statuses

Use `backlog <command> --help` before running unfamiliar commands. Help shows options, fields, and examples.

Do not edit Backlog task, draft, document, decision, or milestone markdown files directly. Use the `backlog` CLI so metadata, relationships, and history stay consistent.

<!-- BACKLOG.MD GUIDELINES END -->
