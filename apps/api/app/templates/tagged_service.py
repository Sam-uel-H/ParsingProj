from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import (
    BusinessValidationError,
    ConflictError,
    InvalidOperationError,
    NotFoundError,
)
from app.documents.models import (
    Document,
    DocumentExtraction,
    DocumentPage,
    DocumentTextBlock,
    ExtractionStatus,
)
from app.templates.models import Template, TemplateColumn, TemplateVersion, TemplateVersionStatus
from app.templates.tagged_models import TaggedExample
from app.templates.tagged_schemas import TaggedExampleWrite


def _draft_version(db: Session, template_id: uuid.UUID) -> tuple[Template, TemplateVersion]:
    template = db.get(Template, template_id)
    if template is None:
        raise NotFoundError("Template")
    if template.archived_at is not None:
        raise InvalidOperationError("Archived templates cannot be tagged.")
    version = db.scalar(
        select(TemplateVersion)
        .where(TemplateVersion.template_id == template.id)
        .order_by(TemplateVersion.version_number.desc())
        .limit(1)
    )
    if version is None or version.status != TemplateVersionStatus.DRAFT:
        raise InvalidOperationError("Tags can only be changed on a draft template version.")
    return template, version


def _require_column(db: Session, version_id: uuid.UUID, column_id: uuid.UUID) -> None:
    column = db.get(TemplateColumn, column_id)
    if column is None or column.template_version_id != version_id:
        raise BusinessValidationError("The selected column is not in the current draft.")


def normalize_with_offsets(value: str) -> tuple[str, list[int], list[int]]:
    characters: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    for index, character in enumerate(value):
        normalized = " " if character.isspace() else character
        if normalized == " " and characters and characters[-1] == " ":
            ends[-1] = index + 1
        else:
            characters.append(normalized)
            starts.append(index)
            ends.append(index + 1)
    return "".join(characters), starts, ends


def _map_selection(
    db: Session, extraction: DocumentExtraction, page_number: int, selected_text: str
) -> tuple[str, int, int, list[str]]:
    page = db.scalar(
        select(DocumentPage).where(
            DocumentPage.extraction_id == extraction.id,
            DocumentPage.page_number == page_number,
        )
    )
    if page is None:
        raise BusinessValidationError("The selected page is not in this extraction.")
    normalized_page, starts, ends = normalize_with_offsets(page.text)
    normalized_selection = normalize_with_offsets(selected_text)[0].strip()
    first = normalized_page.find(normalized_selection)
    if first < 0:
        raise BusinessValidationError("Selection could not be mapped to extracted page text.")
    if normalized_page.find(normalized_selection, first + 1) >= 0:
        raise BusinessValidationError("Selection is ambiguous on this page. Select more context.")

    local_start, local_end = starts[first], ends[first + len(normalized_selection) - 1]
    page_start = sum(
        len(text) + 1
        for text in db.scalars(
            select(DocumentPage.text)
            .where(
                DocumentPage.extraction_id == extraction.id,
                DocumentPage.page_number < page_number,
            )
            .order_by(DocumentPage.page_number)
        )
    )
    start, end = page_start + local_start, page_start + local_end
    full_text = extraction.full_text or ""
    if full_text[start:end] != page.text[local_start:local_end]:
        raise BusinessValidationError("Selection offsets do not match the stored extraction.")

    blocks = list(
        db.scalars(
            select(DocumentTextBlock)
            .where(DocumentTextBlock.page_id == page.id)
            .order_by(DocumentTextBlock.reading_order)
        )
    )
    overlapping = [block for block in blocks if block.char_start < end and block.char_end > start]
    if not overlapping:
        raise BusinessValidationError("Selection has no matching extracted text blocks.")
    covered = bytearray(end - start)
    for block in overlapping:
        for index in range(max(start, block.char_start), min(end, block.char_end)):
            covered[index - start] = 1
    if any(
        not covered[index] and not character.isspace()
        for index, character in enumerate(full_text[start:end])
    ):
        raise BusinessValidationError("Selection crosses text that cannot be mapped to blocks.")
    return full_text[start:end], start, end, [str(block.id) for block in overlapping]


def _validated_selection(
    db: Session, template_id: uuid.UUID, data: TaggedExampleWrite
) -> tuple[str, int, int, list[str]]:
    template, version = _draft_version(db, template_id)
    _require_column(db, version.id, data.template_column_id)
    document = db.get(Document, data.document_id)
    if document is None:
        raise NotFoundError("Document")
    if document.domain_id != template.domain_id:
        raise BusinessValidationError("Sample document and template must have the same domain.")
    extraction = db.get(DocumentExtraction, data.document_extraction_id)
    if (
        extraction is None
        or extraction.document_id != document.id
        or extraction.status != ExtractionStatus.SUCCEEDED
        or document.active_extraction_id != extraction.id
    ):
        raise BusinessValidationError("Select a successful active document extraction.")
    return _map_selection(db, extraction, data.page_number, data.selected_text)


def list_tagged_examples(
    db: Session, template_id: uuid.UUID, document_id: uuid.UUID
) -> list[TaggedExample]:
    template = db.get(Template, template_id)
    if template is None:
        raise NotFoundError("Template")
    if db.get(Document, document_id) is None:
        raise NotFoundError("Document")
    version_id = db.scalar(
        select(TemplateVersion.id)
        .where(TemplateVersion.template_id == template.id)
        .order_by(TemplateVersion.version_number.desc())
        .limit(1)
    )
    return list(
        db.scalars(
            select(TaggedExample)
            .join(TemplateColumn, TemplateColumn.id == TaggedExample.template_column_id)
            .where(
                TemplateColumn.template_version_id == version_id,
                TaggedExample.document_id == document_id,
            )
            .order_by(TaggedExample.page_number, TaggedExample.created_at)
        )
    )


def create_tagged_example(
    db: Session, template_id: uuid.UUID, data: TaggedExampleWrite, actor: User
) -> TaggedExample:
    tagged_value, start, end, block_ids = _validated_selection(db, template_id, data)
    tag = TaggedExample(
        template_column_id=data.template_column_id,
        document_id=data.document_id,
        document_extraction_id=data.document_extraction_id,
        tagged_value=tagged_value,
        expected_value=data.expected_value.strip(),
        page_number=data.page_number,
        char_start=start,
        char_end=end,
        rectangles=[rectangle.model_dump() for rectangle in data.rectangles],
        text_block_ids=block_ids,
        created_by_id=actor.id,
    )
    db.add(tag)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("A tag already exists for this column and extraction.") from exc
    db.refresh(tag)
    return tag


def replace_tagged_example(
    db: Session, template_id: uuid.UUID, tag_id: uuid.UUID, data: TaggedExampleWrite
) -> TaggedExample:
    tag = db.get(TaggedExample, tag_id)
    if tag is None:
        raise NotFoundError("Tagged example")
    if (
        tag.template_column_id != data.template_column_id
        or tag.document_id != data.document_id
        or tag.document_extraction_id != data.document_extraction_id
    ):
        raise BusinessValidationError("Replacement must target the same column and extraction.")
    tagged_value, start, end, block_ids = _validated_selection(db, template_id, data)
    tag.tagged_value = tagged_value
    tag.expected_value = data.expected_value.strip()
    tag.page_number = data.page_number
    tag.char_start = start
    tag.char_end = end
    tag.rectangles = [rectangle.model_dump() for rectangle in data.rectangles]
    tag.text_block_ids = block_ids
    db.commit()
    db.refresh(tag)
    return tag


def delete_tagged_example(db: Session, template_id: uuid.UUID, tag_id: uuid.UUID) -> None:
    _, version = _draft_version(db, template_id)
    tag = db.get(TaggedExample, tag_id)
    if tag is None:
        raise NotFoundError("Tagged example")
    _require_column(db, version.id, tag.template_column_id)
    db.delete(tag)
    db.commit()
