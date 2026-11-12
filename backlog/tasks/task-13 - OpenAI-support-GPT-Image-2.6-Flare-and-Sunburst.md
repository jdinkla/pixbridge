---
id: TASK-13
title: 'OpenAI: support GPT Image 2.6 Flare and Sunburst'
status: Done
assignee:
  - '@claude'
created_date: '2026-11-12T14:45:00Z'
updated_date: '2026-11-12T14:47:00Z'
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
- [x] #1 `gpt-image-2.6-flare` and `gpt-image-2.6-sunburst` pass OpenAI validate_params and reach the SDK call
- [x] #2 `xhigh` and `max` quality are accepted for 2.6 models and still rejected for `gpt-image-2`
- [x] #3 Unknown OpenAI model IDs are still rejected locally before any API call
- [x] #4 Unit tests cover the 2.6 models; README, CLAUDE.md, CHANGELOG and CLI help mention 2.6
- [x] #5 Live tests default to the newest cheap/fast model per provider and the OpenAI live tests pass against 2.6 Flare
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add OPENAI_IMAGE_26_MODELS (two aliases, no snapshots) next to OPENAI_IMAGE_25_MODELS in providers/openai.py; add to supported_models.
2. Allow xhigh/max for 2.5 and 2.6; update the error message.
3. Extend unit tests (capabilities, quality acceptance, SDK serialization, CLI).
4. Update README, CLAUDE.md, CHANGELOG, CLI help, docstrings.
5. Point justfile live models at gpt-image-2.6-flare, gemini-3.1-flash-lite-image, grok-imagine-image-2.0; run just check and just test-live.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Live model choice: newest generation per provider, cheapest/fastest tier within it. OpenAI 2.6 Flare and Sunburst have identical token prices; Flare is the one documented for fast iteration. Gemini 3.1 Flash Lite Image is the cheapest 3.1 image model. xAI has a single image tier, so 2.0 is used although third-party listings put it at about twice the price of the unversioned model. The docs do not state whether 2.6 accepts quality `auto`; pixbridge passes it through unverified.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added `gpt-image-2.6-flare` and `gpt-image-2.6-sunburst` to the OpenAI allowlist (OPENAI_IMAGE_26_MODELS, no dated snapshots exist yet). xhigh/max quality is now accepted for 2.5 and 2.6 and still rejected for gpt-image-2; size rules are unchanged. Unit tests extended (SDK request params, real-SDK wire serialization, CLI, unknown 2.6-like IDs rejected locally). README, CLAUDE.md, CHANGELOG, CLI help and docstrings updated. justfile live models now default to gpt-image-2.6-flare, gemini-3.1-flash-lite-image and grok-imagine-image-2.0. Verification: `just check` green (594 unit tests, ruff, mypy); `just test-live` 4/4 passed against the real APIs on 2026-11-12. Not done, possible follow-up: the 2.6-only request options (`complexity`, SVG/GIF output, markup-guided edits) are not exposed.
<!-- SECTION:FINAL_SUMMARY:END -->
