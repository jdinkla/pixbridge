---
id: TASK-15
title: 'OpenAI: decide on GPT Image 2.6 SVG, animated GIF and markup-guided edits'
status: To Do
assignee: []
created_date: '2026-11-12T15:17:00Z'
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
