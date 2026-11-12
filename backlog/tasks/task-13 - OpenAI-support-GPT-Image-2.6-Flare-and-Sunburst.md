---
id: TASK-13
title: 'OpenAI: support GPT Image 2.6 Flare and Sunburst'
status: In Progress
assignee:
  - '@claude'
created_date: '2026-11-12T14:45:00Z'
updated_date: '2026-11-12T14:45:00Z'
labels: []
dependencies: []
references:
  - https://developers.openai.com/api/docs/models/gpt-image-2.6-flare
  - https://developers.openai.com/api/docs/guides/image-generation
priority: medium
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The OpenAI API now lists `gpt-image-2.6-flare` and `gpt-image-2.6-sunburst` (seen via models.list on 2026-11-12), and the image guide recommends them for new integrations. pixbridge rejects them locally because the OpenAI `supported_models` allowlist stops at 2.5. The live integration tests should run against the newest cheap/fast model per provider, which for OpenAI is 2.6 Flare, so the allowlist gap blocks that too. Per the OpenAI docs: 2.6 has no dated snapshots yet, accepts quality low/medium/high/xhigh/max like 2.5, and uses the same size rules as 2 / 2.5. 2.6 also adds a `complexity` request field plus SVG/GIF output and markup-guided edits; those are out of scope here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `gpt-image-2.6-flare` and `gpt-image-2.6-sunburst` pass OpenAI validate_params and reach the SDK call
- [ ] #2 `xhigh` and `max` quality are accepted for 2.6 models and still rejected for `gpt-image-2`
- [ ] #3 Unknown OpenAI model IDs are still rejected locally before any API call
- [ ] #4 Unit tests cover the 2.6 models; README, CLAUDE.md, CHANGELOG and CLI help mention 2.6
- [ ] #5 Live tests default to the newest cheap/fast model per provider and the OpenAI live tests pass against 2.6 Flare
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add OPENAI_IMAGE_26_MODELS (two aliases, no snapshots) next to OPENAI_IMAGE_25_MODELS in providers/openai.py; add to supported_models.
2. Allow xhigh/max for 2.5 and 2.6; update the error message.
3. Extend unit tests (capabilities, quality acceptance, SDK serialization, CLI).
4. Update README, CLAUDE.md, CHANGELOG, CLI help, docstrings.
5. Point justfile live models at gpt-image-2.6-flare, gemini-3.1-flash-lite-image, grok-imagine-image-2.0; run just check and just test-live.
<!-- SECTION:PLAN:END -->
