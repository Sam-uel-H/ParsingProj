# Phase 6 architecture decisions

## Corrections preserve extraction output

`canonical_value` remains the original normalized LLM result. Reviewer edits are stored separately
as `reviewed_value`, with `human_verified`, `reviewed_by_id`, and `reviewed_at` recording the
single current review state. Full immutable correction history remains deferred to Phase 12.

## Review uses the parsing validator boundary

Human corrections pass through the same deterministic validators used by the parsing engine. A
correction is saved only after it normalizes successfully for the template column type, and a saved
correction clears the result's validation error and marks the value as human-verified.

## Exports prefer reviewed values

CSV and JSON exports follow template display order. Exports use `reviewed_value` when present and
fall back to the original canonical value otherwise. Values that still need review are exported as
blank CSV cells or JSON nulls when no valid canonical value exists.
