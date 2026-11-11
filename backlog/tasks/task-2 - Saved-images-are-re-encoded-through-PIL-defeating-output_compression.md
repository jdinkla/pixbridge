---
id: TASK-2
title: Saved images are re-encoded through PIL, defeating output_compression
status: To Do
assignee: []
created_date: '2026-11-11T15:02:00Z'
labels:
  - client
  - opus
dependencies: []
priority: high
type: bug
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ImageClient._save_image, ImageClient.style_transfer_image and consistency_check._generate_one open the provider's bytes with PIL and call image.save(), which re-encodes at PIL defaults. Reproduced: a JPEG returned at output_compression=95 (1.23 MB) is written as 567 KB (PIL default quality 75). This silently defeats output_compression, adds a second lossy pass for jpeg/webp, and drops embedded metadata. When style_transfer_image writes to an output_path whose extension differs from the returned mime type, the current code converts format implicitly — keep that conversion only for that mismatch case.

**Delegation:** can be delegated to Opus — scope and expected behaviour are fully specified here; no open design decision.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Bytes on disk are identical to GenerationResult.image_data whenever the target extension matches the returned mime type (all three call sites)
- [ ] #2 Corrupt/undecodable image data still raises before a file is left on disk
- [ ] #3 Tests compare bytes written to bytes received for png, jpeg and webp
<!-- AC:END -->
