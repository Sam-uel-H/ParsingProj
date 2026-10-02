from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class DocumentFileType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TIFF = "tiff"
    PNG = "png"
    JPEG = "jpeg"
    TEXT = "text"


class DocumentUploadStatus(StrEnum):
    STORED = "stored"


class DocumentProcessingStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExtractionStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Document(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("file_size > 0", name="file_size_positive"),
        CheckConstraint("char_length(checksum_sha256) = 64", name="checksum_sha256_length"),
    )

    domain_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("domains.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[DocumentFileType] = mapped_column(
        Enum(DocumentFileType, name="document_file_type", native_enum=False), nullable=False
    )
    content_type: Mapped[str] = mapped_column(String(150), nullable=False)
    object_storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    upload_status: Mapped[DocumentUploadStatus] = mapped_column(
        Enum(DocumentUploadStatus, name="document_upload_status", native_enum=False),
        nullable=False,
    )
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        Enum(
            DocumentProcessingStatus,
            name="document_processing_status",
            native_enum=False,
        ),
        nullable=False,
    )
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    active_extraction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_extractions.id", ondelete="RESTRICT", use_alter=True), nullable=True
    )


class DocumentExtraction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_extractions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_extractions_document_version"),
    )

    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus, name="extraction_status", native_enum=False), nullable=False
    )
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentPage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint(
            "extraction_id",
            "page_number",
            name="uq_document_pages_extraction_page_number",
        ),
        CheckConstraint("page_number >= 1", name="page_number_positive"),
        CheckConstraint("width > 0 AND height > 0", name="dimensions_positive"),
    )

    extraction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_extractions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    preview_object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    preview_content_type: Mapped[str] = mapped_column(String(100), nullable=False)


class DocumentTextBlock(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_text_blocks"
    __table_args__ = (
        CheckConstraint("reading_order >= 0", name="reading_order_nonnegative"),
        CheckConstraint("char_start >= 0 AND char_end >= char_start", name="offsets_valid"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="confidence_range"
        ),
    )

    page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    reading_order: Mapped[int] = mapped_column(Integer, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    polygon: Mapped[list[dict[str, float]]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
