# Phase 3 architecture decisions

## Local files implement the object-storage boundary

Development stores originals beneath one configured filesystem root through `ObjectStorage`.
PostgreSQL stores only metadata and an opaque object key. This is the smallest useful local setup,
does not require MinIO, and keeps an S3-compatible production adapter possible without changing the
document module.

Storage keys are generated from server-owned document UUIDs and verified to remain beneath the
configured root. User file names are retained only as sanitized display/download metadata and never
participate in storage paths.

## Upload verification is content-first

The backend identifies PDF, DOCX, TIFF, PNG, JPEG, and UTF-8 text using signatures or structural
checks. It then requires the extension and submitted MIME type to agree with the detected content.
Every accepted file receives a SHA-256 checksum and is rejected before storage if it is empty or
exceeds the configured byte limit.

## Batch results are isolated per file

The multipart endpoint supports one or many files and returns an explicit result for each. The
frontend sends selected files independently so it can display per-file transfer progress. Metadata
is committed separately for each successful original; validation or storage failure for one file
does not roll back unrelated successes.

## Extraction remains a later transition

New documents have `stored` upload status and `pending` processing status. Phase 3 does not invoke
document extraction, OCR, generate previews, or send content externally. Those state transitions
belong to Phase 4 as required by the development plan.
