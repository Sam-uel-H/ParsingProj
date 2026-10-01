from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class ParsingJobStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


class ResultValidationStatus(StrEnum):
    VALID = "valid"
    NEEDS_REVIEW = "needs_review"


class InvocationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ParsingJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "parsing_jobs"
    __table_args__ = (
        Index("ix_parsing_jobs_document_started", "document_id", "started_at"),
        Index("ix_parsing_jobs_template_version_id", "template_version_id"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("template_versions.id"), nullable=False
    )
    status: Mapped[ParsingJobStatus] = mapped_column(
        Enum(ParsingJobStatus, native_enum=False), nullable=False
    )
    domain_override: Mapped[bool] = mapped_column(nullable=False, default=False)
    started_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ParsingResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "parsing_results"
    __table_args__ = (
        UniqueConstraint(
            "parsing_job_id",
            "template_column_id",
            name="uq_parsing_results_parsing_job_id",
        ),
        CheckConstraint("retry_count >= 0", name="retry_count_nonnegative"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_range",
        ),
        Index(
            "ix_parsing_results_job_validation", "parsing_job_id", "validation_status"
        ),
    )

    parsing_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("parsing_jobs.id", ondelete="CASCADE"), nullable=False
    )
    template_column_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("template_columns.id"), nullable=False
    )
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_status: Mapped[ResultValidationStatus] = mapped_column(
        Enum(ResultValidationStatus, native_enum=False), nullable=False
    )
    validation_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LLMInvocation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "llm_invocations"
    __table_args__ = (
        UniqueConstraint(
            "parsing_job_id",
            "template_column_id",
            "attempt_number",
            name="uq_llm_invocations_job_column_attempt",
        ),
        CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        Index("ix_llm_invocations_parsing_job_id", "parsing_job_id"),
    )

    parsing_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("parsing_jobs.id", ondelete="CASCADE"), nullable=False
    )
    template_column_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("template_columns.id"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[InvocationStatus] = mapped_column(
        Enum(InvocationStatus, native_enum=False), nullable=False
    )
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
