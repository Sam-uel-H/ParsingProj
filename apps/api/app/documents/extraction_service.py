from __future__ import annotations

import asyncio
import html
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.errors import InvalidOperationError, NotFoundError
from app.documents.models import (
    Document,
    DocumentExtraction,
    DocumentPage,
    DocumentProcessingStatus,
    DocumentTextBlock,
    ExtractionStatus,
)
from app.documents.schemas import (
    DocumentExtractionRead,
    DocumentPageRead,
    TextBlockRead,
)
from app.jobs.models import BackgroundTask
from app.jobs.schemas import TaskProgress
from app.providers.document_extraction import (
    DocumentExtractionProvider,
    DocumentExtractionRequest,
    ExtractedDocument,
    ExtractedPage,
    Point,
    TextBlock,
)
from app.providers.errors import ProviderError
from app.providers.object_storage import ObjectStorage


@dataclass(frozen=True, slots=True)
class CanonicalPage:
    page: ExtractedPage
    width: float
    height: float
    blocks: tuple[TextBlock, ...]


def _polygon(block: TextBlock, width: float, height: float) -> tuple[Point, ...]:
    if block.polygon:
        return block.polygon
    top = min(max(20.0 + block.reading_order * 18.0, 0), height - 1)
    bottom = min(top + 15.0, height)
    return (Point(20, top), Point(width - 20, top), Point(width - 20, bottom), Point(20, bottom))


def _normalize(result: ExtractedDocument) -> list[CanonicalPage]:
    if not result.pages:
        raise ProviderError("The extractor returned no pages.")
    pages: list[CanonicalPage] = []
    for expected, page in enumerate(result.pages, 1):
        if page.page_number != expected:
            raise ProviderError("Extractor page numbers are not sequential.")
        width, height = page.width or 612.0, page.height or 792.0
        normalized: list[TextBlock] = []
        for block in page.blocks:
            if block.page_number != page.page_number:
                raise ProviderError("A text block references the wrong page.")
            if not (0 <= block.char_start <= block.char_end <= len(result.full_text)):
                raise ProviderError("A text block has invalid character offsets.")
            polygon = _polygon(block, width, height)
            if any(
                point.x < 0 or point.x > width or point.y < 0 or point.y > height
                for point in polygon
            ):
                raise ProviderError("A text block lies outside the page dimensions.")
            normalized.append(
                TextBlock(
                    block.page_number,
                    block.text,
                    block.reading_order,
                    block.char_start,
                    block.char_end,
                    polygon,
                    block.confidence,
                )
            )
        pages.append(CanonicalPage(page, width, height, tuple(normalized)))
    return pages


def _svg(page: CanonicalPage) -> bytes:
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{page.width}" height="{page.height}" '
        f'viewBox="0 0 {page.width} {page.height}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    for block in page.blocks:
        polygon = block.polygon or ()
        x = min((point.x for point in polygon), default=20)
        y = max((point.y for point in polygon), default=40)
        lines.append(
            f'<text x="{x}" y="{y}" font-family="Arial" font-size="12">'
            f"{html.escape(block.text)}</text>"
        )
    if not page.blocks:
        lines.append(
            '<text x="20" y="40" font-family="Arial" font-size="12" fill="#666">'
            "No machine-readable text on this page.</text>"
        )
    lines.append("</svg>")
    return "".join(lines).encode()


def queue_extraction(
    db: Session,
    document_id: uuid.UUID,
    max_attempts: int,
    *,
    reprocess: bool = False,
) -> BackgroundTask:
    document = db.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if document is None:
        raise NotFoundError("Document")
    if document.processing_status in {
        DocumentProcessingStatus.QUEUED,
        DocumentProcessingStatus.PROCESSING,
    }:
        task = db.scalar(
            select(BackgroundTask).where(
                BackgroundTask.extraction_id == document.active_extraction_id
            )
        )
        if task is not None:
            db.commit()
            return task
        raise InvalidOperationError("An extraction is already running.")
    if not reprocess and document.processing_status != DocumentProcessingStatus.PENDING:
        raise InvalidOperationError("Use reprocess to create a new extraction version.")
    version = (
        db.scalar(
            select(func.max(DocumentExtraction.version_number)).where(
                DocumentExtraction.document_id == document.id
            )
        )
        or 0
    )
    extraction = DocumentExtraction(
        document_id=document.id, version_number=version + 1, status=ExtractionStatus.QUEUED
    )
    db.add(extraction)
    db.flush()
    document.active_extraction_id = extraction.id
    document.processing_status = DocumentProcessingStatus.QUEUED
    task = BackgroundTask(extraction_id=extraction.id, max_attempts=max_attempts, total_units=1)
    db.add(task)
    db.commit()
    return task


async def execute_extraction(
    db: Session,
    extraction_id: uuid.UUID,
    storage: ObjectStorage,
    provider: DocumentExtractionProvider,
    timeout_seconds: float,
) -> DocumentExtraction:
    extraction = db.get(DocumentExtraction, extraction_id)
    if extraction is None:
        raise NotFoundError("Document extraction")
    document = db.get(Document, extraction.document_id)
    if document is None:
        raise NotFoundError("Document")
    if extraction.status == ExtractionStatus.SUCCEEDED:
        return extraction

    preview_keys: list[str] = []
    try:
        content = await storage.get(document.object_storage_key)
        result = await asyncio.wait_for(
            provider.extract(
                DocumentExtractionRequest(
                    document.original_file_name, content, document.content_type
                )
            ),
            timeout=timeout_seconds,
        )
        pages = _normalize(result)
        for canonical in pages:
            page_number = canonical.page.page_number
            if document.content_type == "application/pdf":
                preview_key = document.object_storage_key
                preview_type = document.content_type
            else:
                preview_key = (
                    f"documents/{document.id}/extractions/{extraction.id}/page-{page_number}"
                )
                preview_content = canonical.page.preview_content or _svg(canonical)
                preview_type = canonical.page.preview_content_type or "image/svg+xml"
                await storage.put(preview_key, preview_content, preview_type)
                preview_keys.append(preview_key)
            page_model = DocumentPage(
                extraction_id=extraction.id,
                page_number=page_number,
                text=canonical.page.text,
                width=canonical.width,
                height=canonical.height,
                preview_object_key=preview_key,
                preview_content_type=preview_type,
            )
            db.add(page_model)
            db.flush()
            for block in canonical.blocks:
                db.add(
                    DocumentTextBlock(
                        page_id=page_model.id,
                        text=block.text,
                        reading_order=block.reading_order,
                        char_start=block.char_start,
                        char_end=block.char_end,
                        polygon=[{"x": point.x, "y": point.y} for point in block.polygon or ()],
                        confidence=block.confidence,
                    )
                )
        extraction.status = ExtractionStatus.SUCCEEDED
        extraction.provider_name = result.provider
        extraction.provider_version = result.provider_version
        extraction.full_text = result.full_text
        extraction.completed_at = datetime.now(UTC)
        extraction.error_code = extraction.error_message = None
        document.processing_status = DocumentProcessingStatus.SUCCEEDED
        db.flush()
    except Exception:
        db.rollback()
        for key in preview_keys:
            await storage.delete(key)
        raise
    return extraction


def get_active_extraction(
    db: Session,
    document_id: uuid.UUID,
    extraction_id: uuid.UUID | None = None,
) -> DocumentExtractionRead:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError("Document")
    extraction_id = extraction_id or document.active_extraction_id
    if extraction_id is None:
        raise NotFoundError("Document extraction")
    extraction = db.get(DocumentExtraction, extraction_id)
    if extraction is None or extraction.document_id != document_id:
        raise NotFoundError("Document extraction")
    task = db.scalar(select(BackgroundTask).where(BackgroundTask.extraction_id == extraction.id))
    pages: list[DocumentPageRead] = []
    for page in db.scalars(
        select(DocumentPage)
        .where(DocumentPage.extraction_id == extraction.id)
        .order_by(DocumentPage.page_number)
    ):
        blocks = list(
            db.scalars(
                select(DocumentTextBlock)
                .where(DocumentTextBlock.page_id == page.id)
                .order_by(DocumentTextBlock.reading_order)
            )
        )
        pages.append(
            DocumentPageRead(
                id=page.id,
                page_number=page.page_number,
                text=page.text,
                width=page.width,
                height=page.height,
                preview_content_type=page.preview_content_type,
                blocks=[
                    TextBlockRead.model_validate(block, from_attributes=True) for block in blocks
                ],
            )
        )
    return DocumentExtractionRead(
        version_number=extraction.version_number,
        progress=TaskProgress.model_validate(task) if task else None,
        id=extraction.id,
        document_id=extraction.document_id,
        status=extraction.status,
        provider_name=extraction.provider_name,
        provider_version=extraction.provider_version,
        full_text=extraction.full_text,
        error_code=extraction.error_code,
        error_message=extraction.error_message,
        started_at=extraction.started_at,
        completed_at=extraction.completed_at,
        pages=pages,
    )


def get_page(
    db: Session,
    document_id: uuid.UUID,
    page_number: int,
    extraction_id: uuid.UUID | None = None,
) -> DocumentPage:
    document = db.get(Document, document_id)
    if document is None or document.active_extraction_id is None:
        raise NotFoundError("Document page")
    if extraction_id:
        extraction = db.get(DocumentExtraction, extraction_id)
        if extraction is None or extraction.document_id != document_id:
            raise NotFoundError("Document extraction")
    page = db.scalar(
        select(DocumentPage).where(
            DocumentPage.extraction_id == (extraction_id or document.active_extraction_id),
            DocumentPage.page_number == page_number,
        )
    )
    if page is None:
        raise NotFoundError("Document page")
    return page
