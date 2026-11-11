---
id: TASK-7
title: 'Packaging: ship py.typed and set honest dependency lower bounds'
status: To Do
assignee: []
created_date: '2026-11-11T15:02:00Z'
labels:
  - packaging
  - ci
  - opus
dependencies: []
priority: medium
type: chore
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
pyproject declares the 'Typing :: Typed' classifier but src/pixbridge/py.typed does not exist, so downstream type checkers ignore the package's annotations. Dependency floors are openai>=1.0.0 and google-genai>=1.0.0, but the code uses features from much newer SDKs (multi-image images.edit, moderation, output_format/output_compression, types.ImageConfig); only openai 2.46 / google-genai 2.12 are actually tested, so an install resolving to the declared minimum breaks at runtime.

**Delegation:** can be delegated to Opus — scope and expected behaviour are fully specified here; no open design decision.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 py.typed is included in the built wheel
- [ ] #2 Lower bounds for openai, google-genai and pillow (get_flattened_data needs 11+) are raised to the oldest versions that pass the test suite
- [ ] #3 CI has a job that installs with uv --resolution lowest-direct and runs the tests
<!-- AC:END -->
