---
id: TASK-2
title: Saved images are re-encoded through PIL, defeating output_compression
status: Done
assignee:
  - '@claude'
created_date: '2026-11-11T15:02:00Z'
updated_date: '2026-11-12T13:53:00Z'
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
- [x] #1 Bytes on disk are identical to GenerationResult.image_data whenever the target extension matches the returned mime type (all three call sites)
- [x] #2 Corrupt/undecodable image data still raises before a file is left on disk
- [x] #3 Tests compare bytes written to bytes received for png, jpeg and webp
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Shared helper _write_image_bytes in client.py: fully decode to validate, write bytes verbatim when suffix, mime type and detected format agree, otherwise convert with PIL.
2. Use it in ImageClient._save_image, style_transfer_image and consistency_check._generate_one.
3. Byte-equality tests for png/jpeg/webp at all three call sites, plus corrupt-data and mismatch-conversion tests.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented by an Opus subagent, reviewed and merged by the main session. Verbatim write additionally requires PIL's detected format to match the declared mime type, so a provider that mislabels its bytes still gets converted as before. Validation is verify() plus a full load(), because verify() alone misses truncated JPEGs.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
All three save paths go through one helper, _write_image_bytes, which writes the provider's bytes unchanged when the file extension matches the returned format and converts via PIL only on a mismatch. Corrupt data raises before any file is written. Tests compare bytes written to bytes received for png, jpeg and webp via generate_image, generate_image_with_references, style_transfer_image and the consistency check; they fail against the old code. Full suite: 553 passed; ruff check and mypy clean. CHANGELOG updated.
<!-- SECTION:FINAL_SUMMARY:END -->
