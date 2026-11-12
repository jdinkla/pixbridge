---
id: TASK-1
title: 'OpenAI: explicit size is overridden by aspect ratio (4K unreachable)'
status: Done
assignee:
  - '@claude'
created_date: '2026-11-11T15:02:00Z'
updated_date: '2026-11-12T13:53:00Z'
labels:
  - openai
  - sizes
dependencies: []
priority: high
type: bug
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
An explicit size passed to ImageClient/CLI for OpenAI is silently replaced whenever an aspect ratio is in play. ImageClient._resolve_size infers an aspect ratio from a WxH/preset size, then OpenAIProvider.generate / generate_with_references let aspect_ratio take precedence over size (providers/openai.py, 'aspect_ratio takes precedence'). Reproduced with a mocked SDK client: size=3840x2160, 2160p and 1080p all send 2048x1152. The CLI generate command always has an aspect ratio (falls back to the YAML's required generation_notes.aspect_ratio), so --size is dead for OpenAI.

Related wrong mappings: RESOLUTION_PRESETS 720p/1080p map OpenAI to 1536x1024 labelled 16:9 (it is 3:2); ASPECT_RATIO_TO_SIZE['4:3'] is 1536x1024 (3:2; 1536x1152 is a true 4:3 and passes validate_openai_size).

The existing unit tests missed this because each layer is mocked in isolation; the regression tests must run client + resolver + provider together with only the SDK client mocked.

**Delegation:** do NOT delegate to Opus — precedence semantics and preset mappings change observable output for downstream callers (Polyptych-media-creator); needs a judgment call on compatibility and a CHANGELOG note.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 An explicit size (WxH or preset) passed via ImageClient or CLI reaches the OpenAI SDK call unchanged when it is valid; aspect ratio maps to a size only when no size is given
- [x] #2 720p/1080p/2160p presets resolve to true 16:9 OpenAI sizes
- [x] #3 ASPECT_RATIO_TO_SIZE 4:3 and 3:4 map to true 4:3 / 3:4 sizes; 3:2 and 2:3 keep 1536x1024 / 1024x1536
- [x] #4 Regression tests mock only the SDK client and assert the size kwarg sent for 3840x2160, 2160p, 1080p and a portrait size, via ImageClient and via the CLI generate command
- [x] #5 CHANGELOG documents the behaviour change
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. OpenAIProvider.generate / generate_with_references: explicit size wins; aspect_ratio maps to a size only when size is None.
2. RESOLUTION_PRESETS openai: 720p -> 1280x720, 1080p -> 2048x1152 (1920x1080 is not divisible by 16), 2160p stays 3840x2160.
3. ASPECT_RATIO_TO_SIZE: 4:3 -> 1536x1152, 3:4 -> 1152x1536; 3:2 / 2:3 unchanged.
4. New tests/pixbridge/test_openai_size_e2e.py: ImageClient + CLI generate with only the OpenAI SDK client mocked.
5. CHANGELOG + README note on the behaviour change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Compatibility call: size wins outright, no opt-out flag. Callers that passed both size and aspect_ratio to OpenAI now get the requested size (cost/latency can change). An invalid explicit size now raises even when an aspect ratio is given. 1080p maps to 2048x1152 because 1920x1080 fails the divisible-by-16 rule.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
OpenAI provider (generate + generate_with_references): an explicit size now wins; aspect_ratio maps to a size only when none is given. Presets: 720p -> 1280x720, 1080p -> 2048x1152, 2160p -> 3840x2160. 4:3 -> 1536x1152, 3:4 -> 1152x1536; 3:2/2:3 unchanged. New tests/pixbridge/test_openai_size_e2e.py runs ImageClient and the CLI generate command with only the SDK client mocked (44 cases; 29 fail on the old code). CHANGELOG and README updated. Full suite: 553 passed; ruff check and mypy clean. Risk: downstream callers (Polyptych-media-creator) that pass both size and aspect ratio will see larger outputs where the size was previously ignored.
<!-- SECTION:FINAL_SUMMARY:END -->
