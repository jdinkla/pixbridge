---
id: TASK-8
title: Enforce ruff format in CI and fix stale CLAUDE.md size list
status: To Do
assignee: []
created_date: '2026-11-11T15:02:00Z'
labels:
  - ci
  - docs
  - opus
dependencies: []
priority: low
type: chore
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ruff format --check currently wants to reformat 16 files; neither 'just check' nor CI runs the formatter check, so formatting drifts. CLAUDE.md's OpenAI capability sizes list omits 1152x2048 and 2048x1152, which are in _OPENAI_RECOMMENDED_SIZES.

**Delegation:** can be delegated to Opus — scope and expected behaviour are fully specified here; no open design decision.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Codebase is formatted with ruff format in a formatting-only commit
- [ ] #2 just check and the CI workflow fail on unformatted code
- [ ] #3 CLAUDE.md size list matches _OPENAI_RECOMMENDED_SIZES
<!-- AC:END -->
