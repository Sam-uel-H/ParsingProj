# Phase 4 architecture decisions

## Canonical extraction is provider-neutral

Provider output is normalized into an extraction, ordered pages, and ordered text blocks. Blocks
carry stable full-document character offsets, page references, confidence, and polygons bounded by
recorded page dimensions. Missing provider coordinates receive deterministic line boxes so later
Prompt Helper work can consume one consistent model.

## Extraction failure never removes the original

Starting extraction creates an active attempt and changes the document from `pending` to
`processing`. Success atomically stores canonical records and preview references. Timeout, provider
failure, invalid geometry, or storage failure records a diagnosable `failed` attempt while retaining
the original object. Reprocessing failed documents remains deferred to Phase 11.

## Local extraction is intentionally limited

The development provider extracts text PDFs with pypdf, DOCX XML, and UTF-8 text. Pillow provides
PNG/JPEG/TIFF dimensions and normalized PNG page previews but performs no OCR. Scanned-document text
therefore remains empty unless tests or deployment inject an OCR-capable provider. No document is
sent to an external service.

PDF previews reuse the retained original, image inputs receive page images, and text/DOCX inputs
receive deterministic SVG page previews. This keeps local setup small while preserving the provider
and object-storage boundaries required for an approved production adapter.
