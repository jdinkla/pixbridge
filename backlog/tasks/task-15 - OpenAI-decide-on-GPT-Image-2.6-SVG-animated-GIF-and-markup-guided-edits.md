---
id: TASK-15
title: 'OpenAI: decide on GPT Image 2.6 SVG, animated GIF and markup-guided edits'
status: To Do
assignee: []
created_date: '2026-11-12T15:17:00Z'
updated_date: '2026-11-12T15:30:00Z'
labels: []
dependencies:
  - TASK-14
references:
  - https://developers.openai.com/api/docs/guides/image-generation
priority: low
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Split out of TASK-14. GPT Image 2.6 can return SVG (generations endpoint only, n=1, no streaming) and animated GIF (`frame_count` 2-16, `frame_duration_ms` 20-2000), and supports markup-guided edits. pixbridge exposes none of these. Unlike `complexity` (done in TASK-14) they change how output is saved and checked: new file types, the integrity check, frame parameters, and a markup input for edits. There is no known use case yet, so this was deferred rather than built speculatively. Facts are from the OpenAI image guide as read on 2026-11-12 via a summarised fetch; re-verify against the API reference and a live request first.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of SVG output, animated GIF output and markup-guided edits is either supported end to end (ImageClient and CLI) or documented in the README as unsupported, with the reason
- [ ] #2 Supported output types are saved byte-exact with the right extension and handled (or explicitly skipped) by the integrity check
- [ ] #3 Options only 2.6 accepts are rejected locally for other models before any API call
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Carried over from TASK-14 (2026-11-12), relevant when this is picked up: (1) The installed openai SDK (2.46.0) has no named parameters for 2.6-only options; TASK-14 sends `complexity` via `extra_body`, which the SDK merges into the JSON body (generations) and the multipart form (edits). `OpenAIProvider._complexity_kwargs` is the pattern to follow, and the real-SDK wire test `test_complexity_real_sdk_serialization` shows how to assert it. Check first whether a newer SDK adds named parameters. (2) The model gate already exists: `OPENAI_IMAGE_26_MODELS` plus the 2.6-only check in `OpenAIProvider.validate_params`; capability flags live on `ProviderCapabilities` (see `complexity_levels`). (3) `ImageClient` passes provider-specific options only when set, after a capability check, so other providers keep their signatures (`ImageClient._complexity_kwargs`). (4) Live behaviour seen on images/generations: the API returns 400 with `param` and a clear message for unsupported options on gpt-image-2 and 2.5, so a live probe is a cheap way to confirm each option before building. (5) Output handling to review: `OpenAIProvider._OUTPUT_FORMAT_TO_MIME` and `_normalize_output_format` only know png/jpeg/webp, and the README states the 2.6 SVG/GIF/markup options are not exposed; update that sentence when this lands.
<!-- SECTION:NOTES:END -->
