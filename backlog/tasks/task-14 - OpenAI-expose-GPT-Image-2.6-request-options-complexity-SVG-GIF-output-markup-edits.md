---
id: TASK-14
title: 'OpenAI: expose GPT Image 2.6 complexity option and verify auto quality'
status: In Progress
assignee:
  - '@claude'
created_date: '2026-11-12T15:04:00Z'
updated_date: '2026-11-12T15:17:00Z'
labels: []
dependencies:
  - TASK-13
references:
  - https://developers.openai.com/api/docs/guides/image-generation
  - https://developers.openai.com/api/reference/resources/images
priority: low
ordinal: 14000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
GPT Image 2.6 Flare and Sunburst accept a `complexity` request field that pixbridge did not expose, so callers could not set it through `ImageClient` or the CLI. TASK-13 also left open whether 2.6 accepts quality `auto`, which pixbridge passes through. Scope was narrowed on 2026-11-12: SVG/GIF output and markup-guided edits moved to TASK-15 because they change output saving and have no known use case. Live probe on 2026-11-12 (images/generations, 1024x1024, quality low): 2.6-flare accepts quality `auto`; `complexity` accepts low/medium/high and returns 400 for other values; gpt-image-2 and 2.5-flare reject any `complexity` with 400 "not supported for this image model"; output token usage was identical (824) with complexity low and with it omitted, so it does not change billed output tokens at low quality.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `complexity` (low/medium/high) can be set via ImageClient.generate_image, generate_image_with_references and `pixbridge generate --complexity`, and reaches the OpenAI generations and edits requests
- [ ] #2 `complexity` is rejected locally with a ValueError before any API call for gpt-image-2, 2.5 models, invalid values, and providers without complexity support
- [ ] #3 When `complexity` is not given, nothing is sent and the API default applies
- [ ] #4 Whether 2.6 accepts quality `auto` is verified against the API and validation matches the result
- [ ] #5 Unit tests cover the new parameter and README documents it
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. ProviderCapabilities.complexity_levels (None = unsupported); OpenAI = low/medium/high.
2. BaseImageProvider.validate_params gains complexity: reject when unsupported or invalid. OpenAI adds: requires a 2.6 model.
3. OpenAIProvider.generate / generate_with_references accept complexity and send it via extra_body (installed SDK 2.46 has no named parameter); record it in result metadata.
4. ImageClient.generate_image / generate_image_with_references accept complexity; pass it to the provider only when set, after checking capabilities, so other providers keep their signatures.
5. CLI: `generate --complexity`.
6. Tests (provider mock + real-SDK wire test for both endpoints, base, client, CLI), README/CLAUDE.md/CHANGELOG, one live call through the provider for each endpoint.
<!-- SECTION:PLAN:END -->
