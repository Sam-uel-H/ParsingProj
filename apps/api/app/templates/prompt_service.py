from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import AppError, BusinessValidationError, ConflictError, NotFoundError
from app.documents.models import (
    Document,
    DocumentExtraction,
    DocumentPage,
    DocumentTextBlock,
    ExtractionStatus,
)
from app.parsing.validators import validate_value
from app.providers.errors import ProviderError
from app.providers.llm import ExtractionRequest, LLMColumn, LLMProvider, PromptSuggestionRequest
from app.templates.models import Template, TemplateColumn, TemplateVersion, TemplateVersionStatus
from app.templates.prompt_models import PromptDraft
from app.templates.tagged_models import TaggedExample
from app.templates.tagged_service import normalize_with_offsets


def _column_context(
    db: Session, template_id: uuid.UUID, column_id: uuid.UUID
) -> tuple[Template, TemplateVersion, TemplateColumn]:
    template = db.get(Template, template_id)
    if template is None:
        raise NotFoundError("Template")
    if template.archived_at is not None:
        raise ConflictError("Archived templates cannot change prompts.")
    version = db.scalar(
        select(TemplateVersion)
        .where(TemplateVersion.template_id == template_id)
        .order_by(TemplateVersion.version_number.desc())
        .limit(1)
    )
    if version is None or version.status != TemplateVersionStatus.DRAFT:
        raise ConflictError("Prompt changes require the current draft template version.")
    column = db.get(TemplateColumn, column_id)
    if column is None or column.template_version_id != version.id:
        raise BusinessValidationError("Column is not in the current draft.")
    return template, version, column


def _active_extraction(
    db: Session, template: Template, document_id: uuid.UUID
) -> DocumentExtraction:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError("Document")
    if document.domain_id != template.domain_id:
        raise BusinessValidationError("Sample document and template must have the same domain.")
    extraction = db.get(DocumentExtraction, document.active_extraction_id)
    if extraction is None or extraction.status != ExtractionStatus.SUCCEEDED:
        raise BusinessValidationError("Select a successful active document extraction.")
    return extraction


def _draft_context(
    db: Session, template_id: uuid.UUID, draft_id: uuid.UUID
) -> tuple[Template, TemplateVersion, TemplateColumn, PromptDraft, DocumentExtraction]:
    draft = db.get(PromptDraft, draft_id)
    if draft is None:
        raise NotFoundError("Prompt draft")
    template, version, column = _column_context(db, template_id, draft.template_column_id)
    extraction = _active_extraction(db, template, draft.document_id)
    if extraction.id != draft.document_extraction_id:
        raise ConflictError("This prompt draft belongs to an older document extraction.")
    return template, version, column, draft, extraction


def _llm_column(column: TemplateColumn, prompt: str) -> LLMColumn:
    return LLMColumn(
        column.name,
        column.description or "",
        column.column_type.value,
        prompt,
        tuple(column.enum_values or []),
    )


def list_prompt_drafts(
    db: Session, template_id: uuid.UUID, column_id: uuid.UUID, document_id: uuid.UUID
) -> list[PromptDraft]:
    template, _, _ = _column_context(db, template_id, column_id)
    _active_extraction(db, template, document_id)
    return list(
        db.scalars(
            select(PromptDraft)
            .where(
                PromptDraft.template_column_id == column_id,
                PromptDraft.document_id == document_id,
            )
            .order_by(PromptDraft.created_at.desc(), PromptDraft.id.desc())
        )
    )


async def generate_prompt(
    db: Session,
    template_id: uuid.UUID,
    column_id: uuid.UUID,
    document_id: uuid.UUID,
    actor: User,
    provider: LLMProvider,
    timeout_seconds: float,
) -> PromptDraft:
    template, _, column = _column_context(db, template_id, column_id)
    extraction = _active_extraction(db, template, document_id)
    tag = db.scalar(
        select(TaggedExample).where(
            TaggedExample.template_column_id == column_id,
            TaggedExample.document_extraction_id == extraction.id,
        )
    )
    if tag is None:
        raise BusinessValidationError("Tag an example for this column before generating a prompt.")
    try:
        response = await asyncio.wait_for(
            provider.suggest_prompt(
                PromptSuggestionRequest(
                    _llm_column(column, column.prompt_text or ""), tag.tagged_value
                )
            ),
            timeout_seconds,
        )
    except (ProviderError, TimeoutError) as exc:
        raise AppError("prompt_provider_failed", "Prompt suggestion provider failed.", 502) from exc
    prompt = response.text.strip()
    if not prompt or len(prompt) > 10000:
        raise AppError("invalid_provider_output", "Prompt suggestion was empty or too long.", 502)
    draft = PromptDraft(
        template_column_id=column_id,
        document_id=document_id,
        document_extraction_id=extraction.id,
        expected_value=tag.expected_value,
        suggested_prompt=prompt,
        edited_prompt=prompt,
        dry_runs=[],
        accepted=False,
        provider_name=response.metadata.provider,
        model_name=response.metadata.model,
        created_by_id=actor.id,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def edit_prompt(
    db: Session, template_id: uuid.UUID, draft_id: uuid.UUID, prompt: str
) -> PromptDraft:
    _, _, _, draft, _ = _draft_context(db, template_id, draft_id)
    draft.edited_prompt = prompt
    draft.accepted = False
    db.commit()
    db.refresh(draft)
    return draft


def _verified_evidence(
    db: Session, extraction: DocumentExtraction, quote: str | None
) -> dict[str, Any] | None:
    if not quote or not quote.strip():
        return None
    needle = normalize_with_offsets(quote)[0].strip()
    matches: list[tuple[DocumentPage, int, int, int]] = []
    page_offset = 0
    pages = list(
        db.scalars(
            select(DocumentPage)
            .where(DocumentPage.extraction_id == extraction.id)
            .order_by(DocumentPage.page_number)
        )
    )
    for page in pages:
        text, starts, ends = normalize_with_offsets(page.text)
        position = text.find(needle)
        while position >= 0:
            matches.append(
                (
                    page,
                    page_offset + starts[position],
                    page_offset + ends[position + len(needle) - 1],
                    page_offset,
                )
            )
            position = text.find(needle, position + 1)
        page_offset += len(page.text) + 1
    if len(matches) != 1:
        return None
    page, start, end, page_start = matches[0]
    full_text = extraction.full_text or ""
    if full_text[start:end] != page.text[start - page_start : end - page_start]:
        return None
    blocks = list(
        db.scalars(
            select(DocumentTextBlock).where(
                DocumentTextBlock.page_id == page.id,
                DocumentTextBlock.char_start < end,
                DocumentTextBlock.char_end > start,
            )
        )
    )
    covered = bytearray(end - start)
    for block in blocks:
        for index in range(max(start, block.char_start), min(end, block.char_end)):
            covered[index - start] = 1
    if any(
        not covered[index] and not character.isspace()
        for index, character in enumerate(full_text[start:end])
    ):
        return None
    rectangles: list[dict[str, float]] = []
    for block in blocks:
        points = block.polygon or []
        if not points:
            continue
        left = min(point["x"] for point in points) / page.width
        top = min(point["y"] for point in points) / page.height
        right = max(point["x"] for point in points) / page.width
        bottom = max(point["y"] for point in points) / page.height
        rectangles.append({"x": left, "y": top, "width": right - left, "height": bottom - top})
    return {
        "quote": full_text[start:end],
        "page_number": page.page_number,
        "char_start": start,
        "char_end": end,
        "rectangles": rectangles,
    }


async def dry_run(
    db: Session,
    template_id: uuid.UUID,
    draft_id: uuid.UUID,
    provider: LLMProvider,
    timeout_seconds: float,
) -> PromptDraft:
    _, _, column, draft, extraction = _draft_context(db, template_id, draft_id)
    run: dict[str, Any] = {
        "prompt": draft.edited_prompt,
        "created_at": datetime.now(UTC).isoformat(),
        "expected_value": draft.expected_value,
    }
    try:
        response = await asyncio.wait_for(
            provider.extract(
                ExtractionRequest(
                    document_text=extraction.full_text or "",
                    columns=(_llm_column(column, draft.edited_prompt),),
                )
            ),
            timeout_seconds,
        )
        if len(response.values) != 1 or response.values[0].column_name != column.name:
            raise ValueError("Provider returned an unexpected column result.")
        value = response.values[0]
        canonical, message = validate_value(value.value, column.column_type, column.enum_values)
        expected, expected_error = validate_value(
            draft.expected_value, column.column_type, column.enum_values
        )
        evidence = _verified_evidence(db, extraction, value.supporting_text)
        run.update(
            status="valid" if message is None else "invalid",
            actual_value=canonical,
            raw_output=value.raw_output,
            validation_message=message,
            matches_expected=(message is None and expected_error is None and canonical == expected),
            evidence=evidence,
            evidence_verified=evidence is not None,
            provider_name=response.metadata.provider,
            model_name=response.metadata.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=response.usage.latency_ms,
        )
    except (ProviderError, TimeoutError, ValueError, TypeError, IndexError) as exc:
        run.update(
            status="provider_error",
            validation_message=str(exc) or "Provider failed.",
            evidence=None,
            evidence_verified=False,
        )
    draft.dry_runs = [*draft.dry_runs, run]
    db.commit()
    db.refresh(draft)
    return draft


def accept_prompt(
    db: Session,
    template_id: uuid.UUID,
    draft_id: uuid.UUID,
    expected_lock_version: int,
    actor: User,
) -> PromptDraft:
    template, version, column, draft, _ = _draft_context(db, template_id, draft_id)
    locked = db.scalar(
        select(TemplateVersion).where(TemplateVersion.id == version.id).with_for_update()
    )
    assert locked is not None
    if locked.lock_version != expected_lock_version:
        raise ConflictError("Template changed in another tab. Reload before accepting the prompt.")
    column.prompt_text = draft.edited_prompt
    column.updated_by_id = actor.id
    draft.accepted = True
    locked.lock_version += 1
    locked.updated_by_id = actor.id
    template.updated_by_id = actor.id
    db.commit()
    db.refresh(draft)
    return draft
