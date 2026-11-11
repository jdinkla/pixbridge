---
id: TASK-3
title: >-
  Reference images: make missing/unsupported handling consistent across
  providers
status: To Do
assignee: []
created_date: '2026-11-11T15:02:00Z'
labels:
  - gemini
  - client
  - opus
dependencies: []
priority: medium
type: bug
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reference-image errors are handled three different ways. OpenAI raises FileNotFoundError for a missing reference. Gemini (providers/gemini.py generate_with_references) silently skips missing files, silently truncates to 6, and still lists the skipped/truncated paths in metadata['reference_images']. ImageClient.generate_image silently drops default_reference_images when the provider does not support references, while generate_image_with_references raises ValueError for the same situation. Silent drops produce off-target images with no signal; the codebase already chose 'raise' for the explicit path.

**Delegation:** can be delegated to Opus — scope and expected behaviour are fully specified here; no open design decision.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Gemini raises FileNotFoundError for a missing reference image, same as OpenAI
- [ ] #2 Gemini logs a warning when more than 6 references are given, and metadata lists only the references actually sent
- [ ] #3 ImageClient with default_reference_images on a provider without reference support raises ValueError instead of silently generating without them
- [ ] #4 Tests cover all three cases
<!-- AC:END -->
