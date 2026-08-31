from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import BusinessValidationError, NotFoundError
from app.documents.models import (
    Document,
    DocumentExtraction,
    DocumentProcessingStatus,
    ExtractionStatus,
)
from app.parsing.models import (
    InvocationStatus,
    LLMInvocation,
    ParsingJob,
    ParsingJobStatus,
    ParsingResult,
    ResultValidationStatus,
)
from app.parsing.schemas import ParsingJobCreate, ParsingJobRead, ParsingResultRead
from app.parsing.validators import validate_value
from app.providers.errors import ProviderError
from app.providers.llm import ExtractionRequest, LLMColumn, LLMProvider
from app.templates.models import Template, TemplateColumn, TemplateVersion, TemplateVersionStatus


def _read_job(db: Session, job: ParsingJob) -> ParsingJobRead:
    results = list(
        db.scalars(
            select(ParsingResult)
            .where(ParsingResult.parsing_job_id == job.id)
            .order_by(ParsingResult.id)
        )
    )
    columns = {column.id: column for column in db.scalars(select(TemplateColumn))}
    return ParsingJobRead(
        id=job.id,
        document_id=job.document_id,
        template_version_id=job.template_version_id,
        status=job.status,
        domain_override=job.domain_override,
        started_by_id=job.started_by_id,
        started_at=job.started_at,
        completed_at=job.completed_at,
        results=[
            ParsingResultRead(
                id=result.id,
                template_column_id=result.template_column_id,
                column_name=columns[result.template_column_id].name,
                raw_output=result.raw_output,
                canonical_value=result.canonical_value,
                validation_status=result.validation_status,
                validation_message=result.validation_message,
                confidence=result.confidence,
                retry_count=result.retry_count,
            )
            for result in results
        ],
    )


async def run_job(
    db: Session,
    data: ParsingJobCreate,
    actor: User,
    provider: LLMProvider,
    retry_limit: int,
    timeout_seconds: float,
) -> ParsingJobRead:
    document = db.get(Document, data.document_id)
    template = db.get(Template, data.template_id)
    if document is None:
        raise NotFoundError("Document")
    if template is None:
        raise NotFoundError("Template")
    version = db.scalar(
        select(TemplateVersion)
        .where(
            TemplateVersion.template_id == template.id,
            TemplateVersion.status == TemplateVersionStatus.PUBLISHED,
        )
        .order_by(TemplateVersion.version_number.desc())
        .limit(1)
    )
    if version is None:
        raise BusinessValidationError("The selected template is not published.")
    if document.processing_status != DocumentProcessingStatus.SUCCEEDED:
        raise BusinessValidationError("The document must finish extraction before parsing.")
    extraction = db.get(DocumentExtraction, document.active_extraction_id)
    if extraction is None or extraction.status != ExtractionStatus.SUCCEEDED:
        raise BusinessValidationError("The document has no successful active extraction.")
    mismatch = document.domain_id != template.domain_id
    if mismatch and not data.confirm_domain_override:
        raise BusinessValidationError(
            "Document and template domains differ. Explicit confirmation is required.",
            details={"requires_domain_override": True},
        )
    columns = list(
        db.scalars(
            select(TemplateColumn)
            .where(TemplateColumn.template_version_id == version.id)
            .order_by(TemplateColumn.display_order)
        )
    )
    job = ParsingJob(
        document_id=document.id,
        template_version_id=version.id,
        status=ParsingJobStatus.RUNNING,
        domain_override=mismatch,
        started_by_id=actor.id,
    )
    db.add(job)
    db.flush()

    warning = False
    for column in columns:
        canonical: str | None = None
        message: str | None = None
        raw: str | None = None
        confidence: float | None = None
        attempts = 0
        for attempt in range(retry_limit + 1):
            attempts = attempt
            llm_column = LLMColumn(
                column.name,
                column.description or "",
                column.column_type.value,
                column.prompt_text or "",
                tuple(column.enum_values or []),
            )
            try:
                response = await asyncio.wait_for(
                    provider.extract(
                        ExtractionRequest(
                            document_text=extraction.full_text or "",
                            columns=(llm_column,),
                            correction_instruction=message,
                        )
                    ),
                    timeout_seconds,
                )
                value = response.values[0] if response.values else None
                raw = value.raw_output if value else None
                confidence = value.confidence if value else None
                db.add(
                    LLMInvocation(
                        parsing_job_id=job.id,
                        template_column_id=column.id,
                        attempt_number=attempt + 1,
                        status=InvocationStatus.SUCCEEDED,
                        provider_name=response.metadata.provider,
                        model_name=response.metadata.model,
                        raw_output=raw,
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                        latency_ms=response.usage.latency_ms,
                    )
                )
                canonical, message = validate_value(
                    value.value if value else None, column.column_type, column.enum_values
                )
                if message is None:
                    break
            except (TimeoutError, ProviderError) as exc:
                message = "LLM provider timed out." if isinstance(exc, TimeoutError) else str(exc)
                db.add(
                    LLMInvocation(
                        parsing_job_id=job.id,
                        template_column_id=column.id,
                        attempt_number=attempt + 1,
                        status=InvocationStatus.FAILED,
                        error_message=message,
                    )
                )
        valid = message is None
        warning = warning or not valid
        db.add(
            ParsingResult(
                parsing_job_id=job.id,
                template_column_id=column.id,
                raw_output=raw,
                canonical_value=canonical,
                validation_status=(
                    ResultValidationStatus.VALID if valid else ResultValidationStatus.NEEDS_REVIEW
                ),
                validation_message=message,
                confidence=confidence,
                retry_count=attempts,
            )
        )
    job.status = ParsingJobStatus.COMPLETED_WITH_WARNINGS if warning else ParsingJobStatus.COMPLETED
    job.completed_at = datetime.now(UTC)
    db.commit()
    return _read_job(db, job)


def get_job(db: Session, job_id: uuid.UUID) -> ParsingJobRead:
    job = db.get(ParsingJob, job_id)
    if job is None:
        raise NotFoundError("Parsing job")
    return _read_job(db, job)
