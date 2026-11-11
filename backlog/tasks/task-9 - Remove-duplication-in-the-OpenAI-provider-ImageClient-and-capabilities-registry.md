---
id: TASK-9
title: >-
  Remove duplication in the OpenAI provider, ImageClient and capabilities
  registry
status: To Do
assignee: []
created_date: '2026-11-11T15:02:00Z'
labels:
  - refactor
  - opus
dependencies:
  - TASK-1
  - TASK-2
priority: low
type: chore
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
OpenAIProvider.generate and generate_with_references share roughly 100 lines (defaults, size/aspect resolution, prompt truncation, extra kwargs, b64/URL response decoding, metadata), which is how fixes end up applied to one path only. ImageClient.generate_image and generate_image_with_references duplicate the same resolve/call/log/save sequence. providers.get_capabilities is an if-chain parallel to the _PROVIDERS registry, so a new provider must be registered in two places. Pure refactor, scheduled after the size and save bugs are fixed to avoid conflicts.

**Delegation:** can be delegated to Opus — scope and expected behaviour are fully specified here; no open design decision.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Shared OpenAI request preparation and response decoding live in one place used by both generate paths
- [ ] #2 ImageClient has one code path for resolve/call/log/save
- [ ] #3 Capabilities lookup is derived from a single provider registration
- [ ] #4 No behaviour change: existing tests pass unmodified apart from private-helper names
<!-- AC:END -->
