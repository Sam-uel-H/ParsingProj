from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
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


class LLMInvocation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "llm_invocations"

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
