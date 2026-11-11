---
id: TASK-6
title: >-
  CLI: derive aspect-ratio choices from provider capabilities; forward size in
  consistency-check
status: To Do
assignee: []
created_date: '2026-11-11T15:02:00Z'
labels:
  - cli
  - opus
dependencies:
  - TASK-1
priority: low
type: enhancement
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The CLI hardcodes --aspect-ratio choices to 16:9/4:3/3:4/9:16/1:1 on generate, style-transfer and consistency-check, so ratios the providers declare (xAI 20:9 and 3:2, OpenAI 3:2 and 2:3) are unreachable from the command line. consistency_check_command forwards the resolved size only for gemini, so --size is ignored for OpenAI. XAIProvider.UNSUPPORTED_ASPECT_RATIOS duplicates what the capabilities allowlist already rejects. Depends on the size/aspect precedence fix so forwarded sizes behave correctly.

**Delegation:** can be delegated to Opus — scope and expected behaviour are fully specified here; no open design decision.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Any aspect ratio in the selected provider's capabilities.aspect_ratios is accepted by the CLI; invalid ones fail with the provider's validation message
- [ ] #2 consistency-check forwards --size to every provider that takes a size
- [ ] #3 Redundant xAI UNSUPPORTED_ASPECT_RATIOS check is removed without changing which ratios are rejected
<!-- AC:END -->
