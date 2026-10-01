# Phase 10 Decisions

## Separate provider operations

Prompt suggestion uses `LLMProvider.suggest_prompt`; a dry run uses `LLMProvider.extract` for one
column. Both remain provider-neutral. The deterministic development provider makes the workflow
testable without a production LLM account. Dry runs never create parsing jobs or alter published
template versions.

## Drafts and acceptance

Each suggestion creates a `prompt_drafts` record tied to one draft-version column, sample document,
and exact extraction. The record keeps suggested and edited prompt text, expected value, provider
and model metadata, and an append-only JSON run history. Saving edits does not change the template;
accepting the prompt updates its draft column under the existing template `lock_version` check.
Published and archived versions reject prompt changes. Older extraction drafts remain stored but
cannot be run or accepted as current work.

## Validation and evidence

Dry runs use the same `validate_value` registry as parsing jobs. The expected value is normalized
through that registry before comparison with the canonical result. Provider failures and malformed
result shapes are recorded as failed runs. A provider evidence quote is highlighted only when it
maps uniquely to stored extraction text and its non-whitespace characters are covered by text
blocks. Unverified quotes produce no highlight; verified block polygons provide page rectangles.

The workspace warns before discarding unsaved edits on column or document changes, app navigation,
and browser unload. Production provider integration, durable jobs, and reprocessing remain later
phases.
