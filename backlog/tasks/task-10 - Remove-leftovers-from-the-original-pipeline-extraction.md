---
id: TASK-10
title: Remove leftovers from the original pipeline extraction
status: To Do
assignee: []
created_date: '2026-11-11T15:02:00Z'
labels:
  - cleanup
dependencies: []
priority: low
type: chore
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
pixbridge was extracted from a slide/anime pipeline and still carries its vocabulary and shims: docstrings referring to 'Task 7', 'Nano-Banana Pro' and 'presentation slides' (models.py, __init__.py); GeminiImageClient, VALID_SIZES, VALID_ASPECT_RATIOS and the ImageClient.api_key property kept for backward compatibility; OpenAIProvider._truncate_prompt hardcoding anime prompt section headers; the exported but unused ImageProvider Protocol next to the BaseImageProvider ABC.

**Delegation:** do NOT delegate to Opus — which shims Polyptych-media-creator / polyptych still import, and whether section-aware truncation stays in the library or moves to the caller, are decisions for the maintainer.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Usage of each compat shim in downstream repos is checked and recorded in the task notes before removal
- [ ] #2 Unused shims are removed (or deprecated with a warning if still used) and the CHANGELOG lists them
- [ ] #3 Docstrings describe pixbridge as a standalone library
- [ ] #4 A decision on anime-specific prompt truncation is recorded and implemented
<!-- AC:END -->
