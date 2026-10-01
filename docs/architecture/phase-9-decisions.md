# Phase 9 Decisions

## Tag ownership

A tagged example belongs to one column in a draft template version, one sample document, and one
successful active extraction. Its extraction ID, page, canonical character offsets, overlapping
text-block IDs, normalized page rectangles, selected value, and expected value are persisted.
Published and archived templates cannot change tags. A column can have one tag per extraction;
replacement updates that tag rather than creating a duplicate.

## Selection mapping

The browser sends selected text and rectangles. The API collapses whitespace in the selection and
the stored extraction page, then requires exactly one match on that page. It translates the match
back to canonical full-text offsets and checks that extracted text blocks cover every non-whitespace
character. Missing, repeated, or uncovered matches fail explicitly; no approximate match is
inferred. Rectangles come from the browser selection and are stored with the exact extraction.

## Preview and stale tags

Prompt Helper uses PDF.js for selectable machine-readable PDFs and the canonical extracted text
view for other files or PDF text that is easier to select there. The document and column panes are
resizable. The UI reloads tags and highlights those tied to the active extraction, while identifying
tags tied to an older extraction as stale. The current extraction API accepts only pending
documents, so reprocessing is not part of Phase 9. Future reprocessing must keep older tags on
their original extraction and require an explicit new tag when mapping changes.

Prompt generation, dry-runs, and refinement remain Phase 10 work.
