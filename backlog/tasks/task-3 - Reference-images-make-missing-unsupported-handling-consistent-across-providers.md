---
id: TASK-3
title: >-
  Reference images: make missing/unsupported handling consistent across
  providers
status: Done
assignee:
  - '@claude'
created_date: '2026-11-11T15:02:00Z'
updated_date: '2026-11-12T13:53:00Z'
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
- [x] #1 Gemini raises FileNotFoundError for a missing reference image, same as OpenAI
- [x] #2 Gemini logs a warning when more than 6 references are given, and metadata lists only the references actually sent
- [x] #3 ImageClient with default_reference_images on a provider without reference support raises ValueError instead of silently generating without them
- [x] #4 Tests cover all three cases
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Gemini generate_with_references: check every reference path up front and raise FileNotFoundError before any API call.
2. Log a warning when more than 6 references are given; build metadata from the list actually sent.
3. ImageClient.generate_image: raise ValueError when default_reference_images is set and the provider lacks reference support (checked at call time so the provider stays lazy).
4. Tests for all three cases.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented by an Opus subagent, reviewed and merged by the main session. Every supplied path is checked, including ones beyond the 6-image cap. Vertex inherits the behaviour from GeminiProvider. The old test_skips_nonexistent_references was replaced because it asserted the silent skip.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Gemini/Vertex now raise FileNotFoundError for a missing reference image (same message as OpenAI), warn when more than 6 references are passed, and report only the references actually sent in metadata. ImageClient.generate_image raises ValueError when default_reference_images is set on a provider without reference support. Tests cover all three cases. Full suite: 553 passed; ruff check and mypy clean. CHANGELOG updated (behaviour change for callers relying on silent skipping).
<!-- SECTION:FINAL_SUMMARY:END -->
