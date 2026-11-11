---
id: TASK-4
title: >-
  style-transfer CLI: support any provider with style transfer, fix exit code
  and aspect
status: To Do
assignee: []
created_date: '2026-11-11T15:02:00Z'
labels:
  - cli
  - style-transfer
  - opus
dependencies: []
priority: medium
type: enhancement
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The style-transfer command hardcodes provider='gemini' (cli.py style_transfer_command) and restricts --size to 1K/2K, although OpenAI also declares supports_style_transfer. The client error text 'Use gemini provider instead' is stale for the same reason. On OpenAI, style_transfer with no aspect ratio falls back to 1024x1024, so a 16:9 input comes back square. Batch mode returns exit code 0 even when every image failed.

**Delegation:** can be delegated to Opus — scope and expected behaviour are fully specified here; no open design decision.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 style-transfer accepts --provider (default gemini) and works with every provider whose capabilities declare supports_style_transfer; --size is validated by the provider, not a hardcoded choices list
- [ ] #2 When neither size nor aspect ratio is given, OpenAI style transfer picks the output size from the input image's aspect ratio instead of 1024x1024
- [ ] #3 Batch mode exits 1 when no image succeeded
- [ ] #4 Error message for unsupported providers lists providers that do support style transfer rather than naming gemini
<!-- AC:END -->
