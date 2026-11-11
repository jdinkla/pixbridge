---
id: TASK-11
title: Accept a plain string prompt in ImageClient
status: To Do
assignee: []
created_date: '2026-11-11T15:02:00Z'
labels:
  - api
dependencies: []
priority: low
type: enhancement
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every generation call requires an ImagePrompt, whose generation_notes (aspect_ratio, key_requirements) is mandatory even though providers only ever send full_prompt. A library caller who just wants to send text must construct ImagePrompt(full_prompt=..., generation_notes=GenerationNotes(aspect_ratio=..., key_requirements=[])). The provider code itself does this dance in OpenAIProvider.style_transfer.

**Delegation:** do NOT delegate to Opus — public API design (str | ImagePrompt vs making generation_notes optional vs both) should be decided by the maintainer first.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ImageClient generation methods can be called with only a prompt string and a model
- [ ] #2 Existing ImagePrompt callers and YAML prompt files keep working unchanged
- [ ] #3 README shows the minimal string-prompt example
<!-- AC:END -->
