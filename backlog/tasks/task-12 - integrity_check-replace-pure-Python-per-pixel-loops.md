---
id: TASK-12
title: 'integrity_check: replace pure-Python per-pixel loops'
status: To Do
assignee: []
created_date: '2026-11-11T15:02:00Z'
labels:
  - performance
  - opus
dependencies: []
priority: low
type: enhancement
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
check_image materialises every pixel as Python objects (get_flattened_data on the alpha channel and the bottom band) and computes counts and standard deviations in Python loops. On a 3840x2160 image that is 8.3M alpha values per file, which makes 'pixbridge check' on a directory of 4K images slow. Pillow's ImageStat / histogram compute the same figures in C.

**Delegation:** can be delegated to Opus — scope and expected behaviour are fully specified here; no open design decision.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Transparency ratio and bottom-band standard deviation are computed without iterating pixels in Python
- [ ] #2 Results are unchanged for the existing test fixtures
- [ ] #3 The type: ignore for get_flattened_data is gone
<!-- AC:END -->
