from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.documents.models import (
    DocumentFileType,
    DocumentProcessingStatus,
    DocumentUploadStatus,
    ExtractionStatus,
)
from app.jobs.schemas import TaskProgress


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    domain_id: uuid.UUID | None
    original_file_name: str
    file_type: DocumentFileType
    content_type: str
    file_size: int
    checksum_sha256: str
    upload_status: DocumentUploadStatus
    processing_status: DocumentProcessingStatus
    uploaded_by_id: uuid.UUID
    uploaded_at: datetime
    active_extraction_id: uuid.UUID | None


class TextBlockRead(BaseModel):
    id: uuid.UUID
    text: str
    reading_order: int
    char_start: int
    char_end: int
    polygon: list[dict[str, float]]
    confidence: float | None


class DocumentPageRead(BaseModel):
    id: uuid.UUID
    page_number: int
    text: str
    width: float
    height: float
    preview_content_type: str
    blocks: list[TextBlockRead]


class DocumentExtractionRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    status: ExtractionStatus
    provider_name: str | None
    provider_version: str | None
    full_text: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    pages: list[DocumentPageRead]
    version_number: int = 1
    progress: TaskProgress | None = None


class UploadErrorRead(BaseModel):
    code: str
    message: str


class DocumentUploadResult(BaseModel):
    file_name: str
    success: bool
    document: DocumentRead | None = None
    error: UploadErrorRead | None = None


class DocumentUploadBatch(BaseModel):
    results: list[DocumentUploadResult]
