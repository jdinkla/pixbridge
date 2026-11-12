---
id: TASK-14
title: >-
  OpenAI: expose GPT Image 2.6 request options (complexity, SVG/GIF output,
  markup edits)
status: In Progress
assignee:
  - '@claude'
created_date: '2026-11-12T15:04:00Z'
updated_date: '2026-11-12T15:15:00Z'
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
GPT Image 2.6 Flare and Sunburst add request options that pixbridge does not expose, so callers cannot use them through `ImageClient` or the CLI: a `complexity` field (low/medium/high, API default high, no separate fee), SVG output (generations endpoint only, n=1, no streaming), animated GIF output (`frame_count` 2-16, `frame_duration_ms` 20-2000) and markup-guided edits. TASK-13 added the 2.6 models to the allowlist and deliberately left these out. Facts above come from the OpenAI image guide as read on 2026-11-12, partly via a summarised fetch, so re-verify against the API reference before implementing. Also unverified: whether 2.6 accepts quality `auto`, which pixbridge currently passes through. Decide per option whether it is worth supporting; `complexity` is the cheapest to add and affects cost/latency, GIF/SVG touch output-format handling and file saving.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each 2.6-only option is either supported end to end (ImageClient and CLI) or explicitly documented as unsupported
- [ ] #2 Options that only 2.6 accepts are rejected locally with a ValueError for gpt-image-2 and 2.5 before any API call
- [ ] #3 Whether 2.6 accepts quality `auto` is verified against the API and validation matches the result
- [ ] #4 Unit tests cover the new parameters and README documents them
<!-- AC:END -->
