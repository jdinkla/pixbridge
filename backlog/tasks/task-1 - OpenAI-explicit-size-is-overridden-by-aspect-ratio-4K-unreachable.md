---
id: TASK-1
title: 'OpenAI: explicit size is overridden by aspect ratio (4K unreachable)'
status: To Do
assignee: []
created_date: '2026-11-11T15:02:00Z'
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
- [ ] #1 An explicit size (WxH or preset) passed via ImageClient or CLI reaches the OpenAI SDK call unchanged when it is valid; aspect ratio maps to a size only when no size is given
- [ ] #2 720p/1080p/2160p presets resolve to true 16:9 OpenAI sizes
- [ ] #3 ASPECT_RATIO_TO_SIZE 4:3 and 3:4 map to true 4:3 / 3:4 sizes; 3:2 and 2:3 keep 1536x1024 / 1024x1536
- [ ] #4 Regression tests mock only the SDK client and assert the size kwarg sent for 3840x2160, 2160p, 1080p and a portrait size, via ImageClient and via the CLI generate command
- [ ] #5 CHANGELOG documents the behaviour change
<!-- AC:END -->
