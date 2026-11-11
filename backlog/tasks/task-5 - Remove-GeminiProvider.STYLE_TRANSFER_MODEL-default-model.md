---
id: TASK-5
title: Remove GeminiProvider.STYLE_TRANSFER_MODEL default model
status: To Do
assignee: []
created_date: '2026-11-11T15:02:00Z'
labels:
  - gemini
  - opus
dependencies: []
priority: medium
type: chore
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
CLAUDE.md states there is no default model anywhere because model names go stale, enforced in BaseImageProvider.validate_params. GeminiProvider.style_transfer violates this with 'model = model or self.STYLE_TRANSFER_MODEL' (gemini-3-pro-image-preview). The CLI already requires --model for style-transfer, so only library callers relying on the implicit default are affected — note it as a breaking change in the CHANGELOG.

**Delegation:** can be delegated to Opus — scope and expected behaviour are fully specified here; no open design decision.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GeminiProvider.style_transfer (and Vertex) raises the standard 'model must be specified' ValueError when model is None
- [ ] #2 STYLE_TRANSFER_MODEL constant is removed and tests updated
- [ ] #3 CHANGELOG notes the breaking change
<!-- AC:END -->
